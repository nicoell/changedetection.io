from loguru import logger
import hashlib
import os
from changedetectionio import strtobool
from changedetectionio.content_fetchers.exceptions import BrowserStepsInUnsupportedFetcher, EmptyReply, \
    Non200ErrorCodeReceived, ContentTypeMismatchError, AllEmptyContentForMultipleURLsError
from changedetectionio.content_fetchers.base import Fetcher


# "html_requests" is listed as the default fetcher in store.py!
class fetcher(Fetcher):
    fetcher_description = "Basic fast Plaintext/HTTP Client"

    def __init__(self, proxy_override=None, custom_browser_connection_url=None):
        super().__init__()
        self.proxy_override = proxy_override
        # browser_connection_url is none because its always 'launched locally'

    def run(self,
            url,
            timeout,
            request_headers,
            request_body,
            request_method,
            ignore_status_codes=False,
            current_include_filters=None,
            is_binary=False,
            empty_pages_are_a_change=False):

        import chardet
        import requests

        if self.browser_steps_get_valid_steps():
            raise BrowserStepsInUnsupportedFetcher(url=url)

        proxies = {}

        # Allows override the proxy on a per-request basis

        # https://requests.readthedocs.io/en/latest/user/advanced/#socks
        # Should also work with `socks5://user:pass@host:port` type syntax.

        if self.proxy_override:
            proxies = {'http': self.proxy_override, 'https': self.proxy_override, 'ftp': self.proxy_override}
        else:
            if self.system_http_proxy:
                proxies['http'] = self.system_http_proxy
            if self.system_https_proxy:
                proxies['https'] = self.system_https_proxy

        # First, handle the scenario where the URL can contain multiple URLs separated by '|'
        split_urls = [u.strip() for u in url.split('|') if u.strip()]

        # If multiple URLs found
        if len(split_urls) > 1:
            if is_binary:
                raise ValueError("Multiple URLs do not support binary fetching.")

            combined_contents = []
            errors = []

            master_url = None
            master_content_type = None
            master_headers = {}

            for single_url in split_urls:
                try:
                    # Attempt to fetch each URL individually
                    session = requests.Session()

                    if strtobool(os.getenv('ALLOW_FILE_URI', 'false')) and single_url.startswith('file://'):
                        from requests_file import FileAdapter
                        session.mount('file://', FileAdapter())

                    r = session.request(
                        method=request_method,
                        data=(request_body.encode('utf-8') if isinstance(request_body, str) else request_body),
                        url=single_url,
                        headers=request_headers,
                        timeout=timeout,
                        proxies=proxies,
                        verify=False
                    )

                    if r.status_code != 200 and not ignore_status_codes:
                        raise Non200ErrorCodeReceived(url=single_url, status_code=r.status_code, page_html=r.text)

                    # If the response doesn't specify encoding, guess it with chardet
                    if not r.headers.get('content-type') or 'charset=' not in r.headers.get('content-type'):
                        detected_encoding = chardet.detect(r.content)['encoding']
                        if detected_encoding:
                            r.encoding = detected_encoding

                    # Check for empty content
                    if not r.content or not len(r.content):
                        logger.debug(f"Requests returned empty content for '{single_url}'")
                        if not empty_pages_are_a_change:
                            raise EmptyReply(url=single_url, status_code=r.status_code)
                        else:
                            logger.debug(
                                f"URL {single_url} gave zero byte content reply with Status Code {r.status_code}, but empty_pages_are_a_change = True")

                    # If we get here, it's a "successful" fetch
                    # If we haven't set the master yet, do so now
                    if master_url is None:
                        master_url = single_url
                        self.status_code = r.status_code
                        self.headers = r.headers
                        # Content-Type might be missing or None, so default to empty string
                        master_content_type = r.headers.get('Content-Type', '')

                    else:
                        # Check for content-type mismatch
                        new_content_type = r.headers.get('Content-Type', '')
                        if new_content_type != master_content_type:
                            raise ContentTypeMismatchError(
                                master_url=master_url,
                                conflicting_url=single_url,
                                master_content_type=master_content_type,
                                new_content_type=new_content_type
                            )

                    combined_contents.append(r.text)

                except Exception as e:
                    # Log the exception and store it
                    logger.exception(f"Failed to fetch URL {single_url}", exc_info=True)
                    errors.append(e)

            # If every URL failed, re-raise the first error
            if not combined_contents:
                if errors:
                    raise errors[0]
                else:
                    raise AllEmptyContentForMultipleURLsError(split_urls)

            # Join all the successful responses
            self.content = "\n".join(combined_contents)
            self.raw_content = self.content.encode('utf-8')

        else:

            session = requests.Session()

            if strtobool(os.getenv('ALLOW_FILE_URI', 'false')) and url.startswith('file://'):
                from requests_file import FileAdapter
                session.mount('file://', FileAdapter())

            r = session.request(method=request_method,
                                data=request_body.encode('utf-8') if type(request_body) is str else request_body,
                                url=url,
                                headers=request_headers,
                                timeout=timeout,
                                proxies=proxies,
                                verify=False)

            # If the response did not tell us what encoding format to expect, Then use chardet to override what `requests` thinks.
            # For example - some sites don't tell us it's utf-8, but return utf-8 content
            # This seems to not occur when using webdriver/selenium, it seems to detect the text encoding more reliably.
            # https://github.com/psf/requests/issues/1604 good info about requests encoding detection
            if not is_binary:
                # Don't run this for PDF (and requests identified as binary) takes a _long_ time
                if not r.headers.get('content-type') or not 'charset=' in r.headers.get('content-type'):
                    encoding = chardet.detect(r.content)['encoding']
                    if encoding:
                        r.encoding = encoding

            self.headers = r.headers

            if not r.content or not len(r.content):
                logger.debug(f"Requests returned empty content for '{url}'")
                if not empty_pages_are_a_change:
                    raise EmptyReply(url=url, status_code=r.status_code)
                else:
                    logger.debug(f"URL {url} gave zero byte content reply with Status Code {r.status_code}, but empty_pages_are_a_change = True")

            # @todo test this
            # @todo maybe you really want to test zero-byte return pages?
            if r.status_code != 200 and not ignore_status_codes:
                # maybe check with content works?
                raise Non200ErrorCodeReceived(url=url, status_code=r.status_code, page_html=r.text)

            self.status_code = r.status_code
            if is_binary:
                # Binary files just return their checksum until we add something smarter
                self.content = hashlib.md5(r.content).hexdigest()
            else:
                self.content = r.text


            self.raw_content = r.content
