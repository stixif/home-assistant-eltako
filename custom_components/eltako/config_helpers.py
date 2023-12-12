from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import CONF_DEVICE, CONF_DEVICES, CONF_NAME, CONF_ID

from eltakobus.util import AddressExpression, b2a
from eltakobus.eep import EEP

from .const import *

# default settings from configuration
DEFAULT_GENERAL_SETTINGS = {
    CONF_FAST_STATUS_CHANGE: False,
    CONF_SHOW_DEV_ID_IN_DEV_NAME: False,
    CONF_ENABLE_TEACH_IN_BUTTONS: False
}

class device_conf(dict):
    """Object representation of config."""
    def __init__(self, config: ConfigType, extra_keys:[str]=[]):
        self.update(config)
        self.id = AddressExpression.parse(config.get(CONF_ID))
        self.eep_string = config.get(CONF_EEP)
        self.eep = EEP.find(self.eep_string)
        if CONF_NAME in config:
            self.name = config.get(CONF_NAME)
        if CONF_GATEWAY_BASE_ID in config:
            self.gateway_base_id = AddressExpression.parse(config.get(CONF_GATEWAY_BASE_ID))
        for ek in extra_keys:
            if ek in config:
                setattr(self, ek, config.get(ek))
        pass

    def get(self, key: str):
        return super().get(key, None)

def get_device_conf(config: ConfigType, key: str, extra_keys:[str]=[]) -> device_conf:
    if config is not None:
        if key in config.keys():
            return device_conf(config.get(key))
    return None

def get_general_settings_from_configuration(hass: HomeAssistant) -> dict:
    settings = DEFAULT_GENERAL_SETTINGS
    if hass and CONF_GERNERAL_SETTINGS in hass.data[DATA_ELTAKO][ELTAKO_CONFIG]:
        settings = hass.data[DATA_ELTAKO][ELTAKO_CONFIG][CONF_GERNERAL_SETTINGS]
    
    # LOGGER.debug(f"General Settings: {settings}")

    return settings


async def async_get_gateway_config(hass: HomeAssistant, CONFIG_SCHEMA: dict, get_integration_config=async_integration_yaml_config) -> dict:
    config = await async_get_home_assistant_config(hass, CONFIG_SCHEMA, get_integration_config)
    # LOGGER.debug(f"config: {config}")
    if CONF_GATEWAY in config:
        if isinstance(config[CONF_GATEWAY], dict) and CONF_DEVICE in config[CONF_GATEWAY]:
            return config[CONF_GATEWAY]
        elif len(config[CONF_GATEWAY]) > 0 and CONF_DEVICE in config[CONF_GATEWAY][0]:
            return config[CONF_GATEWAY][0]
    return None

async def async_find_gateway_config_by_base_id(base_id: AddressExpression, hass: HomeAssistant, CONFIG_SCHEMA: dict, get_integration_config=async_integration_yaml_config) -> dict:
    config = await async_get_home_assistant_config(hass, CONFIG_SCHEMA, get_integration_config)
    if CONF_GATEWAY in config:
        for g in config[CONF_GATEWAY]:
            if g[CONF_BASE_ID].upper() == b2a(base_id[0],'-').upper():
                return g
    return None


async def async_get_gateway_config_serial_port(hass: HomeAssistant, CONFIG_SCHEMA: dict, get_integration_config=async_integration_yaml_config) -> dict:
    gateway_config = await async_get_gateway_config(hass, CONFIG_SCHEMA, get_integration_config)
    if gateway_config is not None and CONF_SERIAL_PATH in gateway_config:
        return gateway_config[CONF_SERIAL_PATH]
    return None

async def async_get_home_assistant_config(hass: HomeAssistant, CONFIG_SCHEMA: dict, get_integration_config=async_integration_yaml_config) -> dict:
    _conf = await get_integration_config(hass, DOMAIN)
    if not _conf or DOMAIN not in _conf:
        LOGGER.warning("No `eltako:` key found in configuration.yaml.")
        # generate defaults
        return CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
    else:
        return _conf[DOMAIN]
    
def get_device_config(config: dict, base_id: AddressExpression) -> dict:
    gateways = config[CONF_GATEWAY]
    for g in gateways:
        if g[CONF_BASE_ID].upper() == b2a(base_id[0],'-').upper():
            return g[CONF_DEVICES]
    return None

async def async_get_list_of_gateways(hass: HomeAssistant, CONFIG_SCHEMA: dict, get_integration_config=async_integration_yaml_config, filter_out: [str]=[]) -> dict:
    config = await async_get_home_assistant_config(hass, CONFIG_SCHEMA, get_integration_config)
    return get_list_of_gateways_by_config(config, filter_out)

def get_list_of_gateways_by_config(config: dict, filter_out: [str]=[]) -> dict:
    """Compiles a list of all gateways in config."""
    result = {}
    if CONF_GATEWAY in config:
        for g in config[CONF_GATEWAY]:
            g_name = g[CONF_NAME]
            g_device = g[CONF_DEVICE]
            g_base_id = g[CONF_BASE_ID]
            if g_base_id not in filter_out:
                result[g_base_id] = get_gateway_name(g_name, g_device, AddressExpression.parse(g_base_id))
    return result

def compare_enocean_ids(id1: bytes, id2: bytes, len=3) -> bool:
    """Compares two bytes arrays. len specifies the length to be checked."""
    for i in range(0,len):
        if id1[i] != id2[i]:
            return False
    return True

def get_gateway_name(dev_name:str, dev_type:str, base_id:AddressExpression) -> str:
    if not dev_name or len(dev_name) == 0:
        dev_name = GATEWAY_DEFAULT_NAME
    dev_name += " - " + dev_type
    return get_device_name(dev_name, base_id, {CONF_SHOW_DEV_ID_IN_DEV_NAME: True})

def get_device_name(dev_name: str, dev_id: AddressExpression, general_config: dict) -> str:
    if general_config[CONF_SHOW_DEV_ID_IN_DEV_NAME]:
        return f"{dev_name} ({b2a(dev_id[0],'-').upper()})"
    else:
        return dev_name
    
def get_id_from_name(dev_name: str) -> AddressExpression:
    return AddressExpression.parse(dev_name.split('(')[1].split(')')[0])
    
def get_bus_event_type(gateway_id :AddressExpression, function_id: str, source_id: AddressExpression = None, data: str=None) -> str:
    event_id = f"{DOMAIN}.gw_{b2a(gateway_id[0],'-').upper()}.{function_id}"
    
    # add source id e.g. switch id
    if source_id is not None:
        event_id += f".sid_{b2a(source_id[0],'-').upper()}"
    
    # add data for better handling in automations
    if data is not None:
        event_id += f".d_{data}"

    return event_id

def convert_button_pos_from_hex_to_str(pos: int) -> str:
    if pos == 0x10:
        return "LB"
    if pos == 0x30:
        return "LT"
    if pos == 0x70:
        return "RT"
    if pos == 0x50:
        return "RB"
    return None