"""
IEC 61850 DO/DA Configuration
เก็บข้อมูล configuration สำหรับ Data Objects และ Data Attributes
ตามมาตรฐาน IEC 61850
"""

from typing import Dict, List, Any, Optional
from enum import Enum


class DataAttributeType(Enum):
    """ประเภทของ Data Attribute ตาม IEC 61850"""
    BOOLEAN = "Boolean"
    INT8 = "INT8"
    INT16 = "INT16" 
    INT32 = "INT32"
    INT64 = "INT64"
    INT8U = "INT8U"
    INT16U = "INT16U"
    INT32U = "INT32U"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"
    ENUMERATED = "Enumerated"
    CODED_ENUM = "CodedEnum"
    OCTET_STRING = "OctetString"
    VISIBLE_STRING = "VisibleString"
    UNICODE_STRING = "UnicodeString"
    TIMESTAMP = "Timestamp"
    QUALITY = "Quality"
    CHECK = "Check"


class StatusValue(Enum):
    """สถานะทั่วไปสำหรับ Boolean และ Double Point"""
    # Boolean values
    FALSE = 0
    TRUE = 1
    
    # Double point values  
    INTERMEDIATE = 0
    OFF = 1
    ON = 2
    BAD_STATE = 3


class ControlModel(Enum):
    """Control models ตาม IEC 61850"""
    STATUS_ONLY = 0
    DIRECT_NORMAL = 1
    SBO_NORMAL = 2  # Select Before Operate
    DIRECT_ENHANCED = 3
    SBO_ENHANCED = 4


# Configuration สำหรับ Common Data Classes (CDC)
CDC_CONFIG = {
    # Single Point Status
    "SPS": {
        "attributes": {
            "stVal": {
                "type": DataAttributeType.BOOLEAN,
                "values": [StatusValue.FALSE, StatusValue.TRUE],
                "fc": "ST",  # Functional Constraint
                "description": "Status value"
            },
            "q": {
                "type": DataAttributeType.QUALITY,
                "fc": "ST",
                "description": "Quality"
            },
            "t": {
                "type": DataAttributeType.TIMESTAMP,
                "fc": "ST", 
                "description": "Timestamp"
            }
        }
    },
    
    # Double Point Status
    "DPS": {
        "attributes": {
            "stVal": {
                "type": DataAttributeType.CODED_ENUM,
                "values": [
                    StatusValue.INTERMEDIATE,
                    StatusValue.OFF,
                    StatusValue.ON,
                    StatusValue.BAD_STATE
                ],
                "fc": "ST",
                "description": "Status value (double point)"
            },
            "q": {
                "type": DataAttributeType.QUALITY,
                "fc": "ST",
                "description": "Quality"
            },
            "t": {
                "type": DataAttributeType.TIMESTAMP,
                "fc": "ST",
                "description": "Timestamp"
            }
        }
    },
    
    # Integer Status
    "INS": {
        "attributes": {
            "stVal": {
                "type": DataAttributeType.INT32,
                "fc": "ST",
                "description": "Integer status value"
            },
            "q": {
                "type": DataAttributeType.QUALITY,
                "fc": "ST",
                "description": "Quality"
            },
            "t": {
                "type": DataAttributeType.TIMESTAMP,
                "fc": "ST",
                "description": "Timestamp"
            }
        }
    },
    
    # Measured Value (Float)
    "MV": {
        "attributes": {
            "mag": {
                "type": DataAttributeType.FLOAT32,
                "fc": "MX",
                "description": "Magnitude",
                "subattributes": {
                    "f": {
                        "type": DataAttributeType.FLOAT32,
                        "description": "Float value"
                    }
                }
            },
            "q": {
                "type": DataAttributeType.QUALITY,
                "fc": "MX",
                "description": "Quality"
            },
            "t": {
                "type": DataAttributeType.TIMESTAMP,
                "fc": "MX",
                "description": "Timestamp"
            },
            "units": {
                "type": DataAttributeType.VISIBLE_STRING,
                "fc": "CF",
                "description": "Engineering units"
            }
        }
    },
    
    # Complex Measured Value
    "CMV": {
        "attributes": {
            "cVal": {
                "type": "Vector",
                "fc": "MX",
                "description": "Complex value",
                "subattributes": {
                    "mag": {
                        "type": DataAttributeType.FLOAT32,
                        "description": "Magnitude"
                    },
                    "ang": {
                        "type": DataAttributeType.FLOAT32,
                        "description": "Angle"
                    }
                }
            },
            "q": {
                "type": DataAttributeType.QUALITY,
                "fc": "MX",
                "description": "Quality"
            },
            "t": {
                "type": DataAttributeType.TIMESTAMP,
                "fc": "MX",
                "description": "Timestamp"
            }
        }
    },
    
    # Single Point Controllable
    "SPC": {
        "attributes": {
            "stVal": {
                "type": DataAttributeType.BOOLEAN,
                "values": [StatusValue.FALSE, StatusValue.TRUE],
                "fc": "ST",
                "description": "Status value"
            },
            "Oper": {
                "type": "Controllable",
                "fc": "CO",
                "description": "Operate",
                "subattributes": {
                    "ctlVal": {
                        "type": DataAttributeType.BOOLEAN,
                        "values": [StatusValue.FALSE, StatusValue.TRUE],
                        "description": "Control value"
                    }
                }
            },
            "ctlModel": {
                "type": DataAttributeType.ENUMERATED,
                "values": list(ControlModel),
                "fc": "CF",
                "description": "Control model"
            }
        }
    },
    
    # Double Point Controllable
    "DPC": {
        "attributes": {
            "stVal": {
                "type": DataAttributeType.CODED_ENUM,
                "values": [
                    StatusValue.INTERMEDIATE,
                    StatusValue.OFF,
                    StatusValue.ON,
                    StatusValue.BAD_STATE
                ],
                "fc": "ST",
                "description": "Status value"
            },
            "Oper": {
                "type": "Controllable",
                "fc": "CO",
                "description": "Operate",
                "subattributes": {
                    "ctlVal": {
                        "type": DataAttributeType.CODED_ENUM,
                        "values": [StatusValue.OFF, StatusValue.ON],
                        "description": "Control value"
                    }
                }
            },
            "ctlModel": {
                "type": DataAttributeType.ENUMERATED,
                "values": list(ControlModel),
                "fc": "CF",
                "description": "Control model"
            }
        }
    },
    
    # Analogue Setting (ASG)
    "ASG": {
        "attributes": {
            "setMag": {
                "type": DataAttributeType.FLOAT32,
                "fc": "SP",
                "description": "Setting magnitude",
                "subattributes": {
                    "f": {
                        "type": DataAttributeType.FLOAT32,
                        "description": "Float value"
                    }
                }
            },
            "units": {
                "type": DataAttributeType.VISIBLE_STRING,
                "fc": "CF",
                "description": "Engineering units"
            },
            "minVal": {
                "type": DataAttributeType.FLOAT32,
                "fc": "CF",
                "description": "Minimum value"
            },
            "maxVal": {
                "type": DataAttributeType.FLOAT32,
                "fc": "CF",
                "description": "Maximum value"
            }
        }
    },
    
    # Integer Setting (ING)
    "ING": {
        "attributes": {
            "setVal": {
                "type": DataAttributeType.INT32,
                "fc": "SP",
                "description": "Setting value"
            },
            "minVal": {
                "type": DataAttributeType.INT32,
                "fc": "CF",
                "description": "Minimum value"
            },
            "maxVal": {
                "type": DataAttributeType.INT32,
                "fc": "CF",
                "description": "Maximum value"
            },
            "stepSize": {
                "type": DataAttributeType.INT32U,
                "fc": "CF", 
                "description": "Step size"
            }
        }
    }
}


# Logical Node specific DO configurations
LN_DO_CONFIG = {
    # Circuit Breaker (XCBR)
    "XCBR": {
        "Pos": {
            "cdc": "DPC",
            "description": "Switch position"
        },
        "BlkOpn": {
            "cdc": "SPC", 
            "description": "Block opening"
        },
        "BlkCls": {
            "cdc": "SPC",
            "description": "Block closing"
        },
        "Loc": {
            "cdc": "SPS",
            "description": "Local operation"
        }
    },
    
    # Measurement Unit (MMXU)
    "MMXU": {
        "TotW": {
            "cdc": "MV",
            "description": "Total active power"
        },
        "TotVAr": {
            "cdc": "MV",
            "description": "Total reactive power"
        },
        "TotVA": {
            "cdc": "MV",
            "description": "Total apparent power"
        },
        "Hz": {
            "cdc": "MV",
            "description": "Frequency"
        },
        "PhV": {
            "cdc": "CMV",
            "description": "Phase voltages",
            "phases": ["phsA", "phsB", "phsC"]
        },
        "A": {
            "cdc": "CMV",
            "description": "Phase currents",
            "phases": ["phsA", "phsB", "phsC"]
        }
    },
    
    # Protection Overcurrent (PTOC)
    "PTOC": {
        "Str": {
            "cdc": "SPS",
            "description": "Start"
        },
        "Op": {
            "cdc": "SPS",
            "description": "Operate"
        },
        "Blk": {
            "cdc": "SPC",
            "description": "Block operation"
        },
        "StrVal": {
            "cdc": "ASG",
            "description": "Start value",
            "attributes": {
                "setMag": {
                    "type": DataAttributeType.FLOAT32,
                    "fc": "SP",
                    "description": "Setting magnitude",
                    "subattributes": {
                        "f": {
                            "type": DataAttributeType.FLOAT32,
                            "description": "Float value"
                        }
                    }
                }
            }
        },
        "OpDlTmms": {
            "cdc": "ING",
            "description": "Operation delay time",
            "attributes": {
                "setVal": {
                    "type": DataAttributeType.INT32,
                    "fc": "SP",
                    "description": "Setting value (milliseconds)"
                }
            }
        },
        "RsDlTmms": {
            "cdc": "ING", 
            "description": "Reset delay time",
            "attributes": {
                "setVal": {
                    "type": DataAttributeType.INT32,
                    "fc": "SP",
                    "description": "Setting value (milliseconds)"
                }
            }
        },
        "TmASt": {
            "cdc": "CSD",
            "description": "Time to start",
            "attributes": {
                "numCyc": {
                    "type": DataAttributeType.INT16U,
                    "fc": "ST",
                    "description": "Number of cycles"
                }
            }
        }
    }
}


class IEC61850Config:
    """Main configuration class for IEC 61850 DO/DA"""
    
    def __init__(self):
        self.cdc_config = CDC_CONFIG
        self.ln_do_config = LN_DO_CONFIG
    
    def get_do_config(self, ln_class: str, do_name: str) -> Optional[Dict]:
        """Get configuration for specific DO"""
        if ln_class in self.ln_do_config:
            if do_name in self.ln_do_config[ln_class]:
                return self.ln_do_config[ln_class][do_name]
        return None
    
    def get_cdc_config(self, cdc_name: str) -> Optional[Dict]:
        """Get Common Data Class configuration"""
        return self.cdc_config.get(cdc_name)
    
    def get_da_values(self, ln_class: str, do_name: str, da_name: str) -> List[Any]:
        """Get possible values for specific DA"""
        do_config = self.get_do_config(ln_class, do_name)
        if not do_config:
            return []
        
        cdc_name = do_config.get('cdc')
        if not cdc_name:
            return []
        
        cdc_config = self.get_cdc_config(cdc_name)
        if not cdc_config:
            return []
        
        attributes = cdc_config.get('attributes', {})
        
        # Handle nested attributes (e.g., Oper.ctlVal)
        if '.' in da_name:
            parts = da_name.split('.')
            current = attributes
            for part in parts:
                if isinstance(current, dict):
                    if part in current:
                        current = current[part]
                    elif 'subattributes' in current and part in current['subattributes']:
                        current = current['subattributes'][part]
                    else:
                        return []
            
            if isinstance(current, dict) and 'values' in current:
                return current['values']
        else:
            # Direct attribute
            if da_name in attributes:
                da_config = attributes[da_name]
                if 'values' in da_config:
                    return da_config['values']
        
        return []
    
    def get_da_type(self, ln_class: str, do_name: str, da_name: str) -> Optional[DataAttributeType]:
        """Get data type for specific DA"""
        do_config = self.get_do_config(ln_class, do_name)
        if not do_config:
            return None
        
        cdc_name = do_config.get('cdc')
        if not cdc_name:
            return None
        
        cdc_config = self.get_cdc_config(cdc_name)
        if not cdc_config:
            return None
        
        attributes = cdc_config.get('attributes', {})
        
        if da_name in attributes:
            return attributes[da_name].get('type')
        
        return None
    
    def format_value(self, value: Any) -> str:
        """Format value for display"""
        if isinstance(value, StatusValue):
            return value.name
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return str(value)


# Global instance
iec61850_config = IEC61850Config()