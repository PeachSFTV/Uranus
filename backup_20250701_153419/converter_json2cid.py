"""
converter_json2cid.py
~~~~~~~~~~~~~~~~~~~~~
Robust JSON to CID/SCD converter with enhanced error handling and vendor namespace support
FIXED VERSION - with FCDA validation and enhanced error handling
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
import xmltodict
from xml.etree import ElementTree as ET
import copy


class JsonToCidConverter:
    
    # Known vendor namespaces
    vendor_namespaces = {
        "sel": "http://www.selinc.com/2006/61850",
        "abb": "http://www.abb.com/61850/2015/SCL_ABBCommunication", 
        "siemens": "http://www.siemens.com/2003/61850",
        "schneider": "http://www.schneider-electric.com/2007/61850",
        "alstom": "http://www.alstom.com/2008/61850"
    }
    
    @staticmethod
    def convert(json_path: Path) -> Path:
        print(f"🔄 Converting JSON: {json_path}")
        
        try:
            # Read and validate JSON
            raw = json_path.read_text(encoding="utf-8")
            scl_obj = json.loads(raw)
            scl = scl_obj.get("SCL", {})
            
            if not scl:
                raise ValueError("Invalid SCL JSON: Missing SCL root element")
            
            # Determine output extension
            out_ext = ".scd" if scl.get("Substation") else ".cid"
            
            # Pre-process data with enhanced FCDA validation
            print("🧹 Pre-processing SCL data...")
            processed_scl = JsonToCidConverter._preprocess_scl_data(scl)
            
            # Build new SCL structure
            new_scl = JsonToCidConverter._build_scl_structure(processed_scl)
            
            # Generate XML
            print("🔨 Generating XML...")
            xml_str = JsonToCidConverter._generate_xml({"SCL": new_scl})
            
            # Validate XML
            print("✅ Validating XML...")
            JsonToCidConverter._validate_xml(xml_str)
            
            # Write output file
            output_path = JsonToCidConverter._write_output_file(json_path, xml_str, out_ext)
            
            print(f"✅ Successfully created: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Conversion failed: {e}")
            raise

    @staticmethod
    def _preprocess_scl_data(scl: dict) -> dict:
        """Pre-process SCL data to clean up issues"""
        # Deep copy to avoid modifying original
        processed = copy.deepcopy(scl)
        
        # Clean vendor attributes and structure
        processed = JsonToCidConverter._clean_vendor_attributes(processed)
        
        # Fix data structure issues
        processed = JsonToCidConverter._fix_data_structure(processed)
        
        # Validate and fix FCDA references (NEW)
        processed = JsonToCidConverter._validate_and_fix_fcda(processed)
        
        # Clean string values
        processed = JsonToCidConverter._clean_all_strings(processed)
        
        return processed

    @staticmethod
    def _validate_and_fix_fcda(scl: dict) -> dict:
        """ตรวจสอบและแก้ไข FCDA ที่ invalid"""
        print("🔍 Validating FCDA references...")
        
        # เก็บ valid references
        valid_refs = set()
        
        # หา IED ทั้งหมด
        ieds = scl.get('IED', [])
        if not isinstance(ieds, list):
            ieds = [ieds] if ieds else []
        
        for ied in ieds:
            if not isinstance(ied, dict):
                continue
                
            ied_name = ied.get('@name', '')
            
            # หา AccessPoint
            aps = ied.get('AccessPoint', [])
            if not isinstance(aps, list):
                aps = [aps] if aps else []
            
            for ap in aps:
                if not isinstance(ap, dict):
                    continue
                    
                server = ap.get('Server', {})
                if not isinstance(server, dict):
                    continue
                
                # หา LDevice
                ldevices = server.get('LDevice', [])
                if not isinstance(ldevices, list):
                    ldevices = [ldevices] if ldevices else []
                
                for ld in ldevices:
                    if not isinstance(ld, dict):
                        continue
                        
                    ld_inst = ld.get('@inst', '')
                    
                    # เก็บ LN0
                    ln0 = ld.get('LN0')
                    if isinstance(ln0, dict):
                        valid_refs.add((ied_name, ld_inst, 'LLN0', ''))
                        
                        # เก็บ DOI ใน LN0
                        dois = ln0.get('DOI', [])
                        if not isinstance(dois, list):
                            dois = [dois] if dois else []
                        
                        for doi in dois:
                            if isinstance(doi, dict):
                                do_name = doi.get('@name', '')
                                if do_name:
                                    valid_refs.add((ied_name, ld_inst, 'LLN0', '', do_name))
                    
                    # เก็บ LN อื่นๆ
                    lns = ld.get('LN', [])
                    if not isinstance(lns, list):
                        lns = [lns] if lns else []
                    
                    for ln in lns:
                        if not isinstance(ln, dict):
                            continue
                            
                        ln_class = ln.get('@lnClass', '')
                        ln_inst = ln.get('@inst', '')
                        
                        if ln_class:
                            valid_refs.add((ied_name, ld_inst, ln_class, ln_inst))
                            
                            # เก็บ DOI ใน LN
                            dois = ln.get('DOI', [])
                            if not isinstance(dois, list):
                                dois = [dois] if dois else []
                            
                            for doi in dois:
                                if isinstance(doi, dict):
                                    do_name = doi.get('@name', '')
                                    if do_name:
                                        valid_refs.add((ied_name, ld_inst, ln_class, ln_inst, do_name))
        
        print(f"Found {len(valid_refs)} valid LN references")
        
        # แก้ไข DataSet
        invalid_count = 0
        fixed_count = 0
        
        def fix_datasets(obj):
            nonlocal invalid_count, fixed_count
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "DataSet":
                        datasets = value if isinstance(value, list) else [value]
                        
                        for ds in datasets:
                            if not isinstance(ds, dict):
                                continue
                                
                            ds_name = ds.get('@name', 'Unknown')
                            
                            # ตรวจสอบและแก้ไข FCDA
                            fcdas = ds.get('FCDA', [])
                            if not isinstance(fcdas, list):
                                fcdas = [fcdas] if fcdas else []
                            
                            valid_fcdas = []
                            for fcda in fcdas:
                                if not isinstance(fcda, dict):
                                    continue
                                
                                # ตรวจสอบ reference
                                ied_name = fcda.get('@iedName', '')
                                ld_inst = fcda.get('@ldInst', '')
                                ln_class = fcda.get('@lnClass', '')
                                ln_inst = fcda.get('@lnInst', '')
                                do_name = fcda.get('@doName', '')
                                
                                # ลองหา reference ทั้ง 2 แบบ
                                ref_key1 = (ied_name, ld_inst, ln_class, ln_inst)
                                ref_key2 = (ied_name, ld_inst, ln_class, ln_inst, do_name)
                                
                                if ref_key1 in valid_refs or ref_key2 in valid_refs:
                                    valid_fcdas.append(fcda)
                                    fixed_count += 1
                                else:
                                    reference_str = f"{ied_name}/{ld_inst}/{ln_class}{ln_inst}"
                                    if do_name:
                                        reference_str += f".{do_name}"
                                    
                                    print(f"⚠️ Removing invalid FCDA: {reference_str} from DataSet '{ds_name}'")
                                    invalid_count += 1
                            
                            ds['FCDA'] = valid_fcdas
                    
                    elif isinstance(value, (dict, list)):
                        fix_datasets(value)
            
            elif isinstance(obj, list):
                for item in obj:
                    fix_datasets(item)
        
        fix_datasets(scl)
        
        if invalid_count > 0:
            print(f"🔧 Fixed {invalid_count} invalid FCDA references")
            print(f"✅ Kept {fixed_count} valid FCDA references")
        else:
            print("✅ All FCDA references are valid")
        
        return scl

    @staticmethod
    def _clean_vendor_attributes(data: Any) -> Any:
        """Clean vendor attributes and ensure proper namespace handling"""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                # Skip problematic d6p attributes completely
                if k.startswith("@d6p") or k == "@xmlns:d6p1" or "d6p" in k:
                    print(f"⚠️  Skipping problematic attribute: {k}")
                    continue
                
                # Handle malformed vendor attributes
                if ":" in k and not k.startswith("@"):
                    # Check if it's a vendor namespace URL in the key
                    vendor_handled = False
                    for prefix, namespace in JsonToCidConverter.vendor_namespaces.items():
                        if namespace in k:
                            # Extract the actual attribute name
                            attr_name = k.split(':')[-1]
                            new_key = f"@{prefix}:{attr_name}"
                            cleaned[new_key] = v
                            vendor_handled = True
                            print(f"🔧 Fixed vendor attribute: {k} -> {new_key}")
                            break
                    
                    if not vendor_handled:
                        # Skip unrecognized namespace URLs
                        if "http://" in k:
                            print(f"⚠️  Skipping unrecognized namespace: {k}")
                            continue
                        else:
                            # Keep other colon-separated keys that aren't URLs
                            cleaned[k] = JsonToCidConverter._clean_vendor_attributes(v) if isinstance(v, (dict, list)) else v
                    continue
                
                # Handle XMLSchema-instance types
                if "XMLSchema-instance:type" in k:
                    cleaned["@xsi:type"] = v
                    continue
                
                # Regular processing
                if isinstance(v, (dict, list)):
                    cleaned_v = JsonToCidConverter._clean_vendor_attributes(v)
                    if cleaned_v or k in JsonToCidConverter.structural_tags:
                        cleaned[k] = cleaned_v
                elif v not in (None, ""):
                    cleaned[k] = v
            
            return cleaned
            
        elif isinstance(data, list):
            return [JsonToCidConverter._clean_vendor_attributes(item) for item in data if item is not None]
        
        return data

    @staticmethod
    def _fix_data_structure(data: Any) -> Any:
        """Fix structural issues in the data"""
        if isinstance(data, dict):
            fixed = {}
            for k, v in data.items():
                # Ensure proper structure for known elements
                if k == "IED" and isinstance(v, dict):
                    # Ensure IED has required attributes
                    if "@name" not in v:
                        v["@name"] = "Unknown_IED"
                
                if isinstance(v, (dict, list)):
                    fixed[k] = JsonToCidConverter._fix_data_structure(v)
                else:
                    fixed[k] = v
            return fixed
            
        elif isinstance(data, list):
            return [JsonToCidConverter._fix_data_structure(item) for item in data if item is not None]
        
        return data

    @staticmethod
    def _clean_all_strings(data: Any) -> Any:
        """Clean all string values in the data structure"""
        if isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                if isinstance(v, str):
                    cleaned[k] = JsonToCidConverter._clean_string_value(v)
                elif isinstance(v, (dict, list)):
                    cleaned[k] = JsonToCidConverter._clean_all_strings(v)
                else:
                    cleaned[k] = v
            return cleaned
            
        elif isinstance(data, list):
            return [JsonToCidConverter._clean_all_strings(item) for item in data]
        
        elif isinstance(data, str):
            return JsonToCidConverter._clean_string_value(data)
        
        return data

    @staticmethod
    def _clean_string_value(value: str) -> str:
        """Clean string value for XML compatibility"""
        if not isinstance(value, str):
            return str(value)
        
        # Remove XML-illegal control characters
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', value)
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Remove BOM
        value = value.lstrip('\ufeff')
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        # Don't escape XML entities here - let xmltodict handle it
        return value

    @staticmethod
    def _build_scl_structure(scl: dict) -> dict:
        """Build proper SCL structure with correct namespaces"""
        new_scl: dict[str, Any] = {}

        # Core namespaces
        new_scl["@xmlns"] = scl.get("@xmlns", "http://www.iec.ch/61850/2003/SCL")
        new_scl["@xmlns:xsi"] = scl.get("@xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        
        # Add vendor namespaces if they're used
        for prefix, namespace in JsonToCidConverter.vendor_namespaces.items():
            if JsonToCidConverter._uses_vendor_prefix(scl, prefix):
                new_scl[f"@xmlns:{prefix}"] = namespace
                print(f"✅ Added vendor namespace: {prefix}")
        
        # Copy any other xmlns declarations
        for k, v in scl.items():
            if k.startswith("@xmlns:") and k not in new_scl:
                # Skip d6p namespaces
                if "d6p" not in k:
                    new_scl[k] = v

        # Meta attributes
        new_scl["@version"] = scl.get("@version", "2007")
        new_scl["@revision"] = scl.get("@revision", "B")

        # Main sections in proper order
        section_order = ["Header", "Substation", "Communication", "IED", "DataTypeTemplates"]
        
        for section in section_order:
            if section in scl:
                print(f"📋 Processing section: {section}")
                new_scl[section] = JsonToCidConverter._clean_section(scl[section], section)

        # Ensure required attributes for IEDs
        JsonToCidConverter._ensure_inst_attributes(new_scl)
        
        # Enhanced dangling FCDA warning
        JsonToCidConverter._warn_on_dangling_fcda(new_scl)

        return new_scl

    @staticmethod
    def _uses_vendor_prefix(data: Any, prefix: str) -> bool:
        """Check if vendor prefix is used in the data"""
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

    @staticmethod
    def _generate_xml(obj: dict) -> str:
        """Generate XML with enhanced error handling"""
        try:
            # Use xmltodict to generate XML
            xml_str = xmltodict.unparse(obj, pretty=False, full_document=False)
            
            # Post-process the XML
            xml_str = JsonToCidConverter._post_process_xml(xml_str)
            
            return xml_str
            
        except Exception as e:
            print(f"❌ XML generation failed: {e}")
            # Try alternative XML generation
            return JsonToCidConverter._alternative_xml_generation(obj)

    @staticmethod
    def _alternative_xml_generation(obj: dict) -> str:
        """Alternative XML generation method"""
        try:
            print("🔄 Trying alternative XML generation...")
            
            # Simplify the object for XML generation
            simplified_obj = JsonToCidConverter._simplify_for_xml(obj)
            
            xml_str = xmltodict.unparse(simplified_obj, pretty=False, full_document=False)
            xml_str = JsonToCidConverter._post_process_xml(xml_str)
            
            print("✅ Alternative XML generation succeeded")
            return xml_str
            
        except Exception as e:
            print(f"❌ Alternative XML generation also failed: {e}")
            raise

    @staticmethod
    def _simplify_for_xml(data):
        """Simplify data structure for XML generation"""
        if isinstance(data, dict):
            simplified = {}
            for key, value in data.items():
                # Skip problematic keys
                if key.startswith('@d6p') or 'd6p' in key:
                    continue
                
                # Ensure valid XML names
                clean_key = re.sub(r'[^\w\-.:@]', '_', str(key))
                
                if isinstance(value, (dict, list)):
                    simplified_value = JsonToCidConverter._simplify_for_xml(value)
                    if simplified_value:  # Only add non-empty values
                        simplified[clean_key] = simplified_value
                elif value not in (None, ''):
                    simplified[clean_key] = str(value)
            
            return simplified
            
        elif isinstance(data, list):
            return [JsonToCidConverter._simplify_for_xml(item) for item in data if item is not None]
        
        else:
            return data

    @staticmethod
    def _post_process_xml(xml: str) -> str:
        """Post-process generated XML to fix issues"""
        # Compact self-closing tags
        xml = re.sub(r"\s+/>", "/>", xml)
        
        # Remove duplicate XMLSchema-instance namespace declarations
        xml = re.sub(
            r'\s+xmlns:(?!xsi)[^=]+="http://www\.w3\.org/2001/XMLSchema-instance"',
            "",
            xml,
        )
        
        # Final cleanup of any remaining illegal characters
        xml = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", xml)
        
        # Fix any remaining encoding issues
        try:
            xml.encode('utf-8')
        except UnicodeEncodeError:
            xml = xml.encode('utf-8', errors='replace').decode('utf-8')
            print("⚠️  Fixed encoding issues in generated XML")
        
        return xml

    @staticmethod
    def _validate_xml(xml_str: str) -> None:
        """Validate generated XML with enhanced error reporting"""
        try:
            ET.fromstring(xml_str.encode('utf-8'))
            print("✅ XML validation passed")
            
        except ET.ParseError as e:
            # Enhanced error reporting
            error_msg = str(e)
            print(f"❌ XML validation failed: {error_msg}")
            
            # Try to provide more context
            if hasattr(e, 'lineno') and hasattr(e, 'offset'):
                lines = xml_str.split('\n')
                if e.lineno <= len(lines):
                    line = lines[e.lineno - 1]
                    print(f"Problem line {e.lineno}: {line[:100]}...")
                    if e.offset:
                        print(f"Problem at position {e.offset}")
            
            # Try to fix common XML issues
            print("🔧 Attempting to fix XML issues...")
            fixed_xml = JsonToCidConverter._fix_xml_issues(xml_str)
            
            # Validate the fixed XML
            try:
                ET.fromstring(fixed_xml.encode('utf-8'))
                print("✅ XML validation passed after fixes")
                return  # Success
            except ET.ParseError as e2:
                print(f"❌ XML still invalid after fixes: {e2}")
            
            raise Exception(f"XML validation failed: {error_msg}")

    @staticmethod
    def _fix_xml_issues(xml_str: str) -> str:
        """Fix common XML issues"""
        # Fix unescaped ampersands
        xml_str = re.sub(r'&(?![a-zA-Z0-9#]+;)', '&amp;', xml_str)
        
        # Fix unescaped < and >
        xml_str = re.sub(r'<(?![/!?a-zA-Z])', '&lt;', xml_str)
        xml_str = re.sub(r'(?<=[^>])>', '&gt;', xml_str)
        
        # Remove invalid XML characters
        xml_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', xml_str)
        
        # Fix malformed tags
        xml_str = re.sub(r'<([^>]*?)([^/])>([^<]*?)</\1>', r'<\1\2>\3</\1>', xml_str)
        
        return xml_str

    @staticmethod
    def _write_output_file(json_path: Path, xml_str: str, out_ext: str) -> Path:
        """Write output file with enhanced error handling"""
        try:
            # Create output directory
            cid_dir = json_path.parent.parent / "cid_file"
            cid_dir.mkdir(parents=True, exist_ok=True)
            
            # Write debug file
            debug_path = json_path.with_suffix(".debug.xml")
            debug_path.write_text(xml_str, encoding="utf-8")
            print(f"📝 Debug file: {debug_path}")
            
            # Write final output
            out_path = cid_dir / f"{json_path.stem}{out_ext}"
            out_path.write_text(xml_str, encoding="utf-8")
            
            # Verify the written file
            if out_path.exists() and out_path.stat().st_size > 0:
                print(f"✅ Output file verification passed: {out_path.stat().st_size} bytes")
            else:
                print(f"⚠️ Output file verification failed")
            
            return out_path
            
        except Exception as e:
            print(f"❌ File writing failed: {e}")
            
            # Try alternative write method
            try:
                print("🔄 Trying alternative file write...")
                alt_path = json_path.parent / f"{json_path.stem}_alt{out_ext}"
                with open(alt_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(xml_str)
                print(f"✅ Alternative file write succeeded: {alt_path}")
                return alt_path
            except Exception as e2:
                print(f"❌ Alternative file write also failed: {e2}")
                raise

    # Keep the existing helper methods but mark them as structural_tags
    structural_tags = {"DO", "SDO", "DA", "BDA", "DataSet", "FCDA"}

    @staticmethod
    def _clean_section(data: Any, section_name: str) -> Any:
        """Clean a section with enhanced vendor attribute handling"""
        S = JsonToCidConverter.structural_tags
        
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                # Skip problematic attributes
                if k.startswith("@d6p") or k == "@xmlns:d6p1":
                    continue
                
                # Handle vendor attributes more carefully
                if ":" in k and not k.startswith("@"):
                    if "XMLSchema-instance:type" in k:
                        out["@xsi:type"] = v
                        continue
                    if "XMLSchema-instance" in k:
                        continue
                    
                    # Handle vendor namespaces in keys
                    vendor_handled = False
                    for prefix, namespace in JsonToCidConverter.vendor_namespaces.items():
                        if namespace in k:
                            attr_name = k.split(':')[-1]
                            out[f"@{prefix}:{attr_name}"] = v
                            vendor_handled = True
                            break
                    
                    if vendor_handled:
                        continue
                    
                    # Skip other HTTP URLs in keys
                    if "http://" in k:
                        continue
                
                # Skip empty values
                if v in (None, ""):
                    continue
                
                # Process nested structures
                if isinstance(v, (dict, list)):
                    v2 = JsonToCidConverter._clean_section(v, f"{section_name}.{k}")
                    if v2 or (k in S):
                        out[k] = v2 if v2 else v
                elif isinstance(v, str):
                    sv = v.strip()
                    if sv:
                        sv = JsonToCidConverter._clean_string_value(sv)
                        if sv:
                            out[k] = sv
                else:
                    out[k] = v
            
            return out
            
        elif isinstance(data, list):
            res = []
            for it in data:
                it2 = JsonToCidConverter._clean_section(it, section_name)
                if it2 or (isinstance(it, dict) and it.keys() & S):
                    res.append(it2 if it2 else it)
            return res
        
        return data

    @staticmethod
    def _ensure_inst_attributes(scl: dict) -> None:
        """Ensure required inst attributes are present"""
        for ied in JsonToCidConverter._as_list(scl.get("IED")):
            for ap in JsonToCidConverter._as_list(ied.get("AccessPoint")):
                srv = ap.get("Server", {})
                for ld in JsonToCidConverter._as_list(srv.get("LDevice")):
                    ld.setdefault("@inst", ld.get("@inst") or ld.get("@ldName") or "LD1")
                    ln0 = ld.get("LN0")
                    if ln0:
                        ln0.setdefault("@inst", ln0.get("@inst", "0"))
                    for ln in JsonToCidConverter._as_list(ld.get("LN")):
                        ln.setdefault("@inst", ln.get("@inst", "1"))

    @staticmethod
    def _warn_on_dangling_fcda(scl: dict) -> None:
        """Enhanced warning about dangling FCDA references"""
        valid = set()
        for ied in JsonToCidConverter._as_list(scl.get("IED")):
            ied_name = ied.get("@name", "")
            for ap in JsonToCidConverter._as_list(ied.get("AccessPoint")):
                srv = ap.get("Server", {})
                for ld in JsonToCidConverter._as_list(srv.get("LDevice")):
                    li = ld.get("@inst")
                    ln0 = ld.get("LN0")
                    if ln0:
                        valid.add((ied_name, li, "LLN0", ln0.get("@inst", "0")))
                    for ln in JsonToCidConverter._as_list(ld.get("LN")):
                        valid.add((ied_name, li, ln.get("@lnClass"), ln.get("@inst", "")))

        dangling_count = 0
        def walk(node):
            nonlocal dangling_count
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == "DataSet":
                        for ds in JsonToCidConverter._as_list(v):
                            ds_name = ds.get('@name', 'Unknown')
                            for fc in JsonToCidConverter._as_list(ds.get("FCDA")):
                                ied_name = fc.get("@iedName", "")
                                tup = (
                                    ied_name,
                                    fc.get("@ldInst"),
                                    fc.get("@lnClass"),
                                    fc.get("@lnInst", ""),
                                )
                                if tup not in valid:
                                    print(f"⚠️  Dangling FCDA {'/'.join(str(x) for x in tup)} in DataSet '{ds_name}'")
                                    dangling_count += 1
                    walk(v)
            elif isinstance(node, list):
                for it in node:
                    walk(it)

        walk(scl)
        
        if dangling_count == 0:
            print("✅ No dangling FCDA references found")
        else:
            print(f"⚠️ Found {dangling_count} dangling FCDA references")

    @staticmethod
    def _as_list(obj):
        """Convert object to list if it isn't already"""
        if obj is None:
            return []
        return obj if isinstance(obj, list) else [obj]


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("json", help="*.json from SCLParser")
    
    try:
        args = p.parse_args()
        result = JsonToCidConverter.convert(Path(args.json))
        print(f"🎉 Conversion completed successfully!")
        print(f"📁 Output file: {result}")
    except Exception as e:
        print(f"💥 Conversion failed with error: {e}")
        exit(1)