"""The base entity for the rest component."""
import logging
from typing import Any

from homeassistant.components.rest.entity import RestEntity
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .data import RestData

_LOGGER = logging.getLogger(__name__)


class MultiscrapeEntity(RestEntity, TemplateEntity):
    """A class for entities using DataUpdateCoordinator."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Any],
        rest: RestData,
        name,
        device_class,
        resource_template,
        force_update,
        icon_template,
    ) -> None:
        """Create the entity that may have a coordinator."""

        super().__init__(
            coordinator,
            rest,
            name,
            device_class,
            resource_template,
            force_update,
        )

        # ideally _icon_template is pass to __init__ of TemplateEntity but MRO doens't want to cooperate and this works as well.
        # Help is welcome!
        self._icon_template = icon_template
        self._unique_id = None

    @property
    def unique_id(self):
        """Return the unique id of this sensor."""
        return self._unique_id

    def _scrape(self, content, select, attribute, index, value_template):

        try:
            if attribute is not None:
                value = content.select(select)[index][attribute]
            else:
                tag = content.select(select)[index]
                if tag.name in ("style", "script", "template"):
                    value = tag.string
                else:
                    value = tag.text

            _LOGGER.debug("Sensor %s selected: %s", self._name, value)
        except IndexError as exception:
            _LOGGER.error("Sensor %s was unable to extract data from HTML", self._name)
            _LOGGER.debug("Exception: %s", exception)
            return

        if value is not None and value_template is not None:
            value = value_template.async_render_with_possible_json_value(value, None)

        return value
