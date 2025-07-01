from __future__ import annotations
import faulthandler
faulthandler.enable()

import json
import logging
import re
from pathlib import Path
import xmltodict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SCLParser:
    """
    Robust SCL Parser with enhanced vendor extension handling
    """

    # Tags that may legally be attribute-only but are still required later
    structural_tags = {"DO", "SDO", "DA", "BDA", "DataSet", "FCDA"}
    
    # Known vendor namespaces with proper handling
    vendor_namespaces = {
        "http://www.selinc.com/2006/61850": "sel",
        "http://www.abb.com/61850/2015/SCL_ABBCommunication": "abb",
        "http://www.siemens.com/2003/61850": "siemens",
        "http://www.schneider-electric.com/2007/61850": "schneider",
        "http://www.alstom.com/2008/61850": "alstom"
    }

    def __init__(self, input_path: str | Path):
        self.src = Path(input_path)
        if self.src.suffix.lower() not in {".scd", ".cid"}:
            logger.info("Skipping unsupported file type: %s", self.src)
            self.supported = False
            return

        self.supported = True
        self.out_root = (self.src.parent / "../after_convert").resolve()
        self.out_dir = self.out_root / self.src.stem
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def convert_to_json(self) -> None:
        if not getattr(self, "supported", False):
            return
        try:
            # Pre-clean the XML file
            cleaned_xml = self._pre_clean_xml_file()
            
            # Parse the cleaned XML
            scl_dict = self._load_xml_from_string(cleaned_xml).get("SCL")
            if not scl_dict:
                logger.warning("Skipping %s: Missing <SCL> root element", self.src)
                return

            # Post-process the data
            scl_dict = self._clean_scl_data(scl_dict)
            scl_dict = self._ensure_communication(scl_dict)
            scl_dict = self._ensure_root_attrs(scl_dict)

            obj = {"SCL": scl_dict}
            obj = self._clean_scl_data(obj)  # final sweep

            # Write with robust error handling
            out_path = self.out_dir / f"{self.src.stem}.json"
            self._write_json_safely(obj, out_path)
            
            logger.info("Wrote JSON: %s", out_path)
        except Exception as e:
            logger.error("Error processing %s: %s", self.src, e)
            raise

    def _pre_clean_xml_file(self) -> str:
        """Pre-clean XML file before parsing"""
        try:
            # Read with error handling
            text = self.src.read_text(encoding="utf-8", errors="replace")
            
            # Remove BOM
            text = text.lstrip("\ufeff")
            
            # Remove XML-illegal control characters (keep tab, LF, CR)
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
            
            # Fix XML entities that might be broken
            text = re.sub(r'&(?![a-zA-Z0-9#]+;)', '&amp;', text)
            
            # Remove or fix problematic vendor namespace declarations
            text = self._fix_vendor_namespaces_in_xml(text)
            
            # Normalize whitespace but preserve structure
            text = re.sub(r'\r\n', '\n', text)  # Normalize line endings
            text = re.sub(r'\r', '\n', text)    # Handle old Mac line endings
            
            logger.info(f"Pre-cleaned XML: {len(text)} characters")
            return text
            
        except Exception as e:
            logger.error(f"Pre-cleaning failed: {e}")
            # Fallback to original file
            return self.src.read_text(encoding="utf-8", errors="ignore")

    def _fix_vendor_namespaces_in_xml(self, text: str) -> str:
        """Fix vendor namespace declarations in raw XML"""
        try:
            # Find and fix malformed vendor namespace declarations
            
            # Fix SEL namespaces
            text = re.sub(
                r'http://www\.selinc\.com/2006/61850:(\w+)',
                r'sel:\1',
                text
            )
            
            # Fix ABB namespaces
            text = re.sub(
                r'http://www\.abb\.com/61850/2015/SCL_ABBCommunication:(\w+)',
                r'abb:\1',
                text
            )
            
            # Remove problematic d6p declarations
            text = re.sub(r'\s+xmlns:d6p[^=]*="[^"]*"', '', text)
            text = re.sub(r'\s+d6p[^=]*="[^"]*"', '', text)
            
            # Ensure vendor namespace declarations exist
            if 'sel:' in text and 'xmlns:sel=' not in text:
                # Add SEL namespace declaration
                text = text.replace(
                    'xmlns="http://www.iec.ch/61850/2003/SCL"',
                    'xmlns="http://www.iec.ch/61850/2003/SCL" xmlns:sel="http://www.selinc.com/2006/61850"'
                )
            
            if 'abb:' in text and 'xmlns:abb=' not in text:
                # Add ABB namespace declaration
                text = text.replace(
                    'xmlns="http://www.iec.ch/61850/2003/SCL"',
                    'xmlns="http://www.iec.ch/61850/2003/SCL" xmlns:abb="http://www.abb.com/61850/2015/SCL_ABBCommunication"'
                )
            
            return text
            
        except Exception as e:
            logger.warning(f"Vendor namespace fix failed: {e}")
            return text

    def _load_xml_from_string(self, xml_text: str) -> dict:
        """Parse XML from string with robust error handling"""
        try:
            # Set up namespace mapping
            namespaces = {
                "http://www.iec.ch/61850/2003/SCL": None,
                "http://www.w3.org/2001/XMLSchema-instance": "xsi",
            }
            
            # Add vendor namespaces
            namespaces.update(self.vendor_namespaces)
            
            # Parse with xmltodict
            parsed = xmltodict.parse(
                xml_text,
                attr_prefix="@",
                process_namespaces=True,
                namespaces=namespaces,
            )
            
            return self._fix_namespace_attrs(parsed)
            
        except Exception as e:
            logger.error(f"XML parsing failed: {e}")
            # Fallback: try without namespace processing
            try:
                parsed = xmltodict.parse(
                    xml_text,
                    attr_prefix="@",
                    process_namespaces=False,
                )
                logger.warning("Parsed without namespace processing")
                return self._fix_namespace_attrs(parsed)
            except Exception as e2:
                logger.error(f"Fallback parsing also failed: {e2}")
                raise

    def _fix_namespace_attrs(self, data):
        """Enhanced namespace attribute fixing"""
        if isinstance(data, dict):
            fixed = {}
            for k, v in data.items():
                # Handle XMLSchema-instance types
                if "http://www.w3.org/2001/XMLSchema-instance:type" in k:
                    fixed["@xsi:type"] = v
                    continue
                
                # Skip problematic d6p attributes
                elif k.startswith("@d6p") or "d6p" in k:
                    logger.debug(f"Skipping d6p attribute: {k}")
                    continue
                
                # Handle vendor namespace attributes properly
                elif ":" in k and not k.startswith("@"):
                    vendor_handled = False
                    
                    # Check each vendor namespace
                    for vendor_url, prefix in self.vendor_namespaces.items():
                        if vendor_url in k:
                            # Extract attribute name
                            attr_name = k.split(':')[-1]
                            fixed[f"@{prefix}:{attr_name}"] = v
                            vendor_handled = True
                            logger.debug(f"Converted vendor attr: {k} -> @{prefix}:{attr_name}")
                            break
                    
                    if not vendor_handled:
                        logger.debug(f"Skipping unhandled namespaced key: {k}")
                        continue
                
                else:
                    # Regular attribute or element
                    if isinstance(v, (dict, list)):
                        fixed[k] = self._fix_namespace_attrs(v)
                    else:
                        fixed[k] = v
            
            return fixed
            
        elif isinstance(data, list):
            return [self._fix_namespace_attrs(item) for item in data]
        
        return data

    def _clean_scl_data(self, scl_dict: dict) -> dict:
        """Enhanced SCL data cleaning"""
        struct_tags = self.structural_tags

        def clean(d):
            if isinstance(d, dict):
                cleaned = {}
                for k, v in d.items():
                    # Skip malformed keys more aggressively
                    if ":" in k and not k.startswith("@"):
                        # Only allow known vendor prefixes
                        prefix = k.split(':')[0]
                        if prefix not in self.vendor_namespaces.values():
                            logger.debug(f"Skipping malformed key: {k}")
                            continue
                    
                    # Handle XMLSchema-instance type
                    if "XMLSchema-instance:type" in k:
                        cleaned["@xsi:type"] = v
                        continue
                    
                    # Skip d6p attributes
                    if k.startswith("@d6p") or "d6p" in k:
                        continue
                    
                    # Skip None values
                    if v is None:
                        continue
                    
                    # Clean string values
                    if isinstance(v, str):
                        v = self._clean_string_value(v)
                        if not v:  # Skip empty strings after cleaning
                            continue
                    
                    # Process nested structures
                    if isinstance(v, (dict, list)):
                        v_clean = clean(v)
                        # Keep node if it has content OR is structural
                        if v_clean or (k in struct_tags):
                            cleaned[k] = v_clean if v_clean else v
                    else:
                        cleaned[k] = v
                
                return cleaned
                
            elif isinstance(d, list):
                cleaned_list = []
                for item in d:
                    if item is None:
                        continue
                    item_clean = clean(item)
                    if item_clean or (
                        isinstance(item, dict) and item.keys() & struct_tags
                    ):
                        cleaned_list.append(item_clean if item_clean else item)
                return cleaned_list
            
            return d

        return clean(scl_dict)

    def _clean_string_value(self, value: str) -> str:
        """Enhanced string value cleaning"""
        if not isinstance(value, str):
            return value
        
        # Remove control characters (keep tab, LF, CR)
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', value)
        
        # Remove null bytes specifically
        value = value.replace('\x00', '')
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        # Basic XML entity check (don't double-escape)
        if '&' in value and not re.search(r'&[a-zA-Z0-9#]+;', value):
            value = value.replace('&', '&amp;')
        
        return value

    def _write_json_safely(self, obj: dict, out_path: Path):
        """Write JSON with proper error handling"""
        try:
            # First attempt with full Unicode support
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
                
        except UnicodeEncodeError:
            logger.warning("Unicode encoding issue, falling back to ASCII-safe mode")
            # Fallback: use ASCII-safe encoding
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=True, indent=2)
                
        except Exception as e:
            logger.error(f"JSON writing failed: {e}")
            raise

    # Rest of the methods remain the same as before...
    def split_into_ied_json(self) -> None:
        self.convert_to_json()

    def _ensure_communication(self, scl_dict: dict) -> dict:
        """Inject a minimal <Communication> element if missing/incomplete."""
        comm = scl_dict.get("Communication", {})

        def _has_cap(section: dict) -> bool:
            subs = section.get("SubNetwork")
            if not subs:
                return False
            subs = subs if isinstance(subs, list) else [subs]
            for sub in subs:
                if isinstance(sub, dict) and "ConnectedAP" in sub:
                    return True
            return False

        if not _has_cap(comm):
            comm = self._create_default_communication(scl_dict)
            logger.info("Injecting default <Communication> into %s", self.src)
        scl_dict["Communication"] = comm
        return scl_dict

    def _ensure_root_attrs(self, scl_dict: dict) -> dict:
        """Guarantee mandatory xmlns / version / revision attributes + vendor namespaces."""
        if "@xmlns" not in scl_dict:
            scl_dict["@xmlns"] = "http://www.iec.ch/61850/2003/SCL"
        if (self._has_xsi_type(scl_dict)) and ("@xmlns:xsi" not in scl_dict):
            scl_dict["@xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
        
        # Add vendor namespaces if they're used
        for prefix, namespace in self.vendor_namespaces.items():
            if self._uses_vendor_prefix(scl_dict, prefix):
                scl_dict[f"@xmlns:{prefix}"] = namespace
                logger.info(f"Added vendor namespace: {prefix}")
        
        scl_dict.setdefault("@version", "2007")
        scl_dict.setdefault("@revision", "B")
        return scl_dict

    def _uses_vendor_prefix(self, data, prefix: str) -> bool:
        """Check if vendor prefix is used in data"""
        def check(obj):
            if isinstance(obj, dict):
                for k in obj.keys():
                    if k.startswith(f"@{prefix}:"):
                        return True
                    if isinstance(obj[k], (dict, list)) and check(obj[k]):
                        return True
            elif isinstance(obj, list):
                return any(check(item) for item in obj)
            return False
        
        return check(data)

    def _has_xsi_type(self, data):
        if isinstance(data, dict):
            for k, v in data.items():
                if k == "@xsi:type" or "XMLSchema-instance:type" in str(k):
                    return True
                if isinstance(v, (dict, list)) and self._has_xsi_type(v):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._has_xsi_type(item):
                    return True
        return False

    def _create_default_communication(self, scl_dict: dict) -> dict:
        try:
            # Use the pre-cleaned XML text
            raw = self._pre_clean_xml_file()
            
            raw = re.sub(r"\sxmlns(:\w+)?=\"[^\"]+\"", "", raw)
            tmp = xmltodict.parse(
                raw,
                attr_prefix="@",
                process_namespaces=True,
                namespaces={"http://www.iec.ch/61850/2003/SCL": None},
            )
            parsed = tmp.get("SCL", {})
            first_ied = parsed.get("IED")
            if isinstance(first_ied, list):
                first_ied = first_ied[0]
            ied_name = (first_ied or {}).get("@name", "IED1")
            aps = (first_ied or {}).get("AccessPoint")
            if isinstance(aps, list):
                aps = aps[0]
            ap_name = (aps or {}).get("@name", "P1")
        except Exception as e:
            logger.warning(f"Failed to extract IED info for default communication: {e}")
            ied_name, ap_name = "IED1", "P1"

        return {
            "SubNetwork": {
                "@name": "StationBus",
                "@type": "8-MMS",
                "ConnectedAP": {
                    "@iedName": ied_name,
                    "@apName": ap_name,
                    "Address": {
                        "P": [
                            {"@type": "IP", "#text": "0.0.0.0"},
                            {"@type": "OSI-AP-title", "#text": "1,3,9999,13"},
                            {"@type": "OSI-AE-qualifier", "#text": "13"},
                            {"@type": "OSI-P-selector", "#text": "00,01"},
                            {"@type": "OSI-S-selector", "#text": "00,01"},
                            {"@type": "OSI-T-selector", "#text": "00,01"},
                        ]
                    },
                },
            }
        }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Robust SCL to JSON converter"
    )
    ap.add_argument("file", help=".scd / .cid path")
    args = ap.parse_args()

    parser = SCLParser(args.file)
    parser.convert_to_json()