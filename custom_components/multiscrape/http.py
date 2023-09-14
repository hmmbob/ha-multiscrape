"""HTTP request related functionality."""
import logging
from collections.abc import Callable
import httpx

from homeassistant.const import HTTP_DIGEST_AUTHENTICATION

_LOGGER = logging.getLogger(__name__)


class HttpWrapper:
    """Class to wrap a httpx request."""

    def __init__(
        self,
        config_name,
        hass,
        client,
        file_manager,
        timeout,
        method: str = None,
        params_renderer: Callable = None,
        request_headers: Callable = None,
        data_renderer: Callable = None,
    ):
        """Initialize HttpWrapper."""
        _LOGGER.debug("%s # Initializing http wrapper", config_name)
        self._client = client
        self._file_manager = file_manager
        self._config_name = config_name
        self._timeout = timeout
        self._hass = hass
        self._auth = None
        self._method = method
        self._params_renderer = params_renderer
        self._request_headers = request_headers
        self._data_renderer = data_renderer

    def set_authentication(self, username, password, auth_type):
        """Set http authentication."""
        if auth_type == HTTP_DIGEST_AUTHENTICATION:
            self._auth = httpx.DigestAuth(username, password)
        else:
            self._auth = (username, password)
        _LOGGER.debug("%s # Authentication configuration processed", self._config_name)

    async def async_request(self, context, resource, method=None, request_data=None):
        """Execute a HTTP request."""
        data = request_data or self._data_renderer()
        method = method or self._method or "GET"

        _LOGGER.debug(
            "%s # Executing %s-request with a %s to url: %s.",
            self._config_name,
            context,
            method,
            resource,
        )
        if self._file_manager:
            await self._async_file_log(
                "request_headers", context, self._request_headers
            )
            await self._async_file_log("request_body", context, data)

        response = None

        try:
            response = await self._client.request(
                method,
                resource,
                headers=self._request_headers,
                params=self._params_renderer(),
                auth=self._auth,
                data=data,
                timeout=self._timeout,
                follow_redirects=True,
            )

            _LOGGER.debug(
                "%s # Response status code received: %s",
                self._config_name,
                response.status_code,
            )
            if self._file_manager:
                await self._async_file_log(
                    "response_headers", context, response.headers
                )
                await self._async_file_log("response_body", context, response.text)

            # bit of a hack since httpx also raises an exception for redirects: https://github.com/encode/httpx/blob/c6c8cb1fe2da9380f8046a19cdd5aade586f69c8/CHANGELOG.md#0200-13th-october-2021
            if 400 <= response.status_code <= 599:
                response.raise_for_status()
            return response
        except httpx.TimeoutException as ex:
            _LOGGER.debug(
                "%s # Timeout error while executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise
        except httpx.RequestError as ex:
            _LOGGER.debug(
                "%s # Request error while executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise
        except Exception as ex:
            _LOGGER.debug(
                "%s # Error executing %s request to url: %s.\n Error message:\n %s",
                self._config_name,
                method,
                resource,
                repr(ex),
            )
            await self._handle_request_exception(context, response)
            raise

    async def _handle_request_exception(self, context, response):
        try:
            if self._file_manager:
                await self._async_file_log(
                    "response_headers_error", context, response.headers
                )
                await self._async_file_log(
                    "response_body_error", context, response.text
                )
        except Exception as exc:
            _LOGGER.debug(
                "%s # Unable to write headers and body to files during handling of exception.\n Error message:\n %s",
                self._config_name,
                repr(exc),
            )

    async def _async_file_log(self, content_name, context, content):
        try:
            filename = f"{context}_{content_name}.txt"
            await self._hass.async_add_executor_job(
                self._file_manager.write, filename, content
            )
        except Exception as ex:
            _LOGGER.error(
                "%s # Unable to write %s to file: %s. \nException: %s",
                self._config_name,
                content_name,
                filename,
                ex,
            )
        _LOGGER.debug(
            "%s # %s written to file: %s",
            self._config_name,
            content_name,
            filename,
        )
