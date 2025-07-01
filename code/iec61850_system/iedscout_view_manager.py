#!/usr/bin/env python3
"""
IEDScout View Manager
~~~~~~~~~~~~~~~~~~~~
Implements authentic IEDScout-style flat view with 3 sections only
"""

from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QBrush
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class IEDScoutItem:
    """IEDScout view item"""
    section: str  # GOOSE, Reports, DataModel
    name: str
    value: str = ""
    description: str = ""
    path: str = ""
    item_type: str = ""  # Type of item
    editable: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class IEDScoutViewManager(QObject):
    """Manages IEDScout-style flat view"""
    
    # Signals
    item_double_clicked = pyqtSignal(object)  # IEDScoutItem
    item_edited = pyqtSignal(object, str)     # IEDScoutItem, new_value
    
    def __init__(self, tree_widget: QTreeWidget):
        super().__init__()
        self.tree = tree_widget
        self.items = []  # All IEDScout items
        # Only 3 sections as requested
        self.sections = {
            'GOOSE': [],
            'Reports': [], 
            'DataModel': []
        }
        
        # Setup tree for IEDScout view
        self.setup_iedscout_view()
    
    def setup_iedscout_view(self):
        """Setup tree widget for IEDScout flat view"""
        # Set headers for IEDScout view
        self.tree.setHeaderLabels([
            "Name",           # Element name
            "Value",          # Current value
            "Description",    # Description/Type
            "Path",           # Full path
            "Section"         # Which section
        ])
        
        # Configure header
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        # Set column widths
        self.tree.setColumnWidth(0, 250)  # Name
        self.tree.setColumnWidth(1, 150)  # Value
        self.tree.setColumnWidth(2, 200)  # Description
        # Path column stretches
        self.tree.setColumnWidth(4, 100)  # Section
    
    def parse_scl_for_iedscout(self, scl_data: dict, selected_ieds: List[str]):
        """Parse SCL data and extract IEDScout sections"""
        self.clear()
        
        if 'SCL' not in scl_data:
            return
        
        ieds = scl_data['SCL'].get('IED', [])
        if not isinstance(ieds, list):
            ieds = [ieds]
        
        # Process each selected IED
        for ied in ieds:
            ied_name = ied.get('@name', 'Unknown')
            if ied_name not in selected_ieds:
                continue
            
            # Extract sections from IED
            self._extract_goose_section(ied, ied_name)
            self._extract_reports_section(ied, ied_name)
            self._extract_datamodel_section(ied, ied_name)
    
    def _extract_goose_section(self, ied: dict, ied_name: str):
        """Extract GOOSE control blocks and data"""
        aps = ied.get('AccessPoint', [])
        if not isinstance(aps, list):
            aps = [aps]
        
        for ap in aps:
            server = ap.get('Server', {})
            lds = server.get('LDevice', [])
            if not isinstance(lds, list):
                lds = [lds]
            
            for ld in lds:
                ld_inst = ld.get('@inst', 'LD0')
                ln0 = ld.get('LN0', {})
                
                if ln0:
                    # GOOSE Control Blocks
                    gses = ln0.get('GSEControl', [])
                    if not isinstance(gses, list):
                        gses = [gses]
                    
                    for gse in gses:
                        item = IEDScoutItem(
                            section='GOOSE',
                            name=gse.get('@name', 'Unknown'),
                            value='Configured',
                            description=f"GOOSE Control Block - AppID: {gse.get('@appID', 'N/A')}",
                            path=f"{ied_name}/{ld_inst}/LLN0.{gse.get('@name', '')}",
                            item_type='GSEControl',
                            metadata={
                                'appID': gse.get('@appID', ''),
                                'datSet': gse.get('@datSet', ''),
                                'confRev': gse.get('@confRev', '1')
                            }
                        )
                        self.sections['GOOSE'].append(item)
                        
                        # Add dataset members if available
                        dataset_name = gse.get('@datSet', '')
                        if dataset_name:
                            self._add_goose_dataset_members(ied, ied_name, ld_inst, dataset_name)
    
    def _add_goose_dataset_members(self, ied: dict, ied_name: str, ld_inst: str, dataset_name: str):
        """Add GOOSE dataset members"""
        # Find dataset definition
        aps = ied.get('AccessPoint', [])
        if not isinstance(aps, list):
            aps = [aps]
        
        for ap in aps:
            server = ap.get('Server', {})
            lds = server.get('LDevice', [])
            if not isinstance(lds, list):
                lds = [lds]
            
            for ld in lds:
                if ld.get('@inst') != ld_inst:
                    continue
                
                ln0 = ld.get('LN0', {})
                if ln0:
                    datasets = ln0.get('DataSet', [])
                    if not isinstance(datasets, list):
                        datasets = [datasets]
                    
                    for ds in datasets:
                        if ds.get('@name') == dataset_name:
                            # Add dataset members
                            fcda_list = ds.get('FCDA', [])
                            if not isinstance(fcda_list, list):
                                fcda_list = [fcda_list]
                            
                            for idx, fcda in enumerate(fcda_list):
                                ln_class = fcda.get('@lnClass', '')
                                ln_inst = fcda.get('@lnInst', '')
                                do_name = fcda.get('@doName', '')
                                da_name = fcda.get('@daName', '')
                                
                                full_path = f"{ied_name}/{ld_inst}/{ln_class}{ln_inst}.{do_name}"
                                if da_name:
                                    full_path += f".{da_name}"
                                
                                item = IEDScoutItem(
                                    section='GOOSE',
                                    name=f"  [{idx}] {do_name}.{da_name}" if da_name else f"  [{idx}] {do_name}",
                                    value='<value>',
                                    description=f"Dataset member - {ln_class}{ln_inst}",
                                    path=full_path,
                                    item_type='GOOSE_DA',
                                    editable=True,
                                    metadata={
                                        'dataset': dataset_name,
                                        'index': idx,
                                        'fc': fcda.get('@fc', 'ST'),
                                        'da_name': da_name,
                                        'do_name': do_name,
                                        'ln_class': ln_class
                                    }
                                )
                                self.sections['GOOSE'].append(item)
    
    def _extract_reports_section(self, ied: dict, ied_name: str):
        """Extract Report Control Blocks"""
        aps = ied.get('AccessPoint', [])
        if not isinstance(aps, list):
            aps = [aps]
        
        for ap in aps:
            server = ap.get('Server', {})
            lds = server.get('LDevice', [])
            if not isinstance(lds, list):
                lds = [lds]
            
            for ld in lds:
                ld_inst = ld.get('@inst', 'LD0')
                
                # Check all LNs for Report Control Blocks
                all_lns = []
                
                # LN0
                ln0 = ld.get('LN0', {})
                if ln0:
                    all_lns.append(('LLN0', '', ln0))
                
                # Other LNs
                lns = ld.get('LN', [])
                if not isinstance(lns, list):
                    lns = [lns]
                
                for ln in lns:
                    ln_class = ln.get('@lnClass', '')
                    ln_inst = ln.get('@inst', '')
                    all_lns.append((ln_class, ln_inst, ln))
                
                # Process each LN
                for ln_class, ln_inst, ln_data in all_lns:
                    ln_name = f"{ln_class}{ln_inst}" if ln_inst else ln_class
                    
                    # Buffered Report Control Blocks
                    rpts = ln_data.get('ReportControl', [])
                    if not isinstance(rpts, list):
                        rpts = [rpts]
                    
                    for rpt in rpts:
                        if rpt:  # Check if not empty
                            item = IEDScoutItem(
                                section='Reports',
                                name=rpt.get('@name', 'Unknown'),
                                value='Buffered' if rpt.get('@buffered', 'false') == 'true' else 'Unbuffered',
                                description=f"Report Control Block - {ln_name}",
                                path=f"{ied_name}/{ld_inst}/{ln_name}.{rpt.get('@name', '')}",
                                item_type='ReportControl',
                                metadata={
                                    'rptID': rpt.get('@rptID', ''),
                                    'datSet': rpt.get('@datSet', ''),
                                    'intgPd': rpt.get('@intgPd', '0'),
                                    'buffered': rpt.get('@buffered', 'false') == 'true'
                                }
                            )
                            self.sections['Reports'].append(item)
    
    def _extract_datamodel_section(self, ied: dict, ied_name: str):
        """Extract complete data model (all DAs)"""
        aps = ied.get('AccessPoint', [])
        if not isinstance(aps, list):
            aps = [aps]
        
        for ap in aps:
            server = ap.get('Server', {})
            lds = server.get('LDevice', [])
            if not isinstance(lds, list):
                lds = [lds]
            
            for ld in lds:
                ld_inst = ld.get('@inst', 'LD0')
                
                # Get all LNs
                all_lns = []
                
                # LN0
                ln0 = ld.get('LN0', {})
                if ln0:
                    all_lns.append(('LLN0', '', ln0))
                
                # Other LNs
                lns = ld.get('LN', [])
                if not isinstance(lns, list):
                    lns = [lns]
                
                for ln in lns:
                    ln_class = ln.get('@lnClass', '')
                    ln_inst = ln.get('@inst', '')
                    all_lns.append((ln_class, ln_inst, ln))
                
                # Process each LN
                for ln_class, ln_inst, ln_data in all_lns:
                    ln_name = f"{ln_class}{ln_inst}" if ln_inst else ln_class
                    
                    # Get DOIs
                    dois = ln_data.get('DOI', [])
                    if not isinstance(dois, list):
                        dois = [dois]
                    
                    for doi in dois:
                        do_name = doi.get('@name', '')
                        
                        # Get DAIs
                        dais = doi.get('DAI', [])
                        if not isinstance(dais, list):
                            dais = [dais]
                        
                        for dai in dais:
                            da_name = dai.get('@name', '')
                            
                            # Get value
                            value = ''
                            vals = dai.get('Val', [])
                            if vals:
                                if not isinstance(vals, list):
                                    vals = [vals]
                                if vals[0] and '#text' in vals[0]:
                                    value = vals[0]['#text']
                            
                            # Full path
                            full_path = f"{ied_name}/{ld_inst}/{ln_name}.{do_name}.{da_name}"
                            
                            # Determine editability
                            editable = self._is_da_editable(da_name, do_name, ln_class)
                            
                            item = IEDScoutItem(
                                section='DataModel',
                                name=f"{ln_name}.{do_name}.{da_name}",
                                value=value,
                                description=self._get_da_description(da_name),
                                path=full_path,
                                item_type='DA',
                                editable=editable,
                                metadata={
                                    'ln_class': ln_class,
                                    'do_name': do_name,
                                    'da_name': da_name,
                                    'sAddr': dai.get('@sAddr', '')
                                }
                            )
                            self.sections['DataModel'].append(item)
    
    def _get_da_description(self, da_name: str) -> str:
        """Get description for data attribute"""
        descriptions = {
            'stVal': 'Status value',
            'mag': 'Magnitude',
            'q': 'Quality',
            't': 'Timestamp',
            'ctlVal': 'Control value',
            'origin': 'Origin',
            'ctlNum': 'Control number',
            'units': 'Units',
            'db': 'Deadband',
            'minVal': 'Minimum value',
            'maxVal': 'Maximum value',
            'stepSize': 'Step size'
        }
        
        return descriptions.get(da_name, 'Data attribute')
    
    def _is_da_editable(self, da_name: str, do_name: str, ln_class: str) -> bool:
        """Check if DA is editable"""
        # Read-only attributes
        readonly = ['q', 't', 'origin', 'ctlNum', 'T', 'timeStamp']
        if da_name in readonly:
            return False
        
        # Control values
        if da_name in ['ctlVal', 'setVal', 'Oper', 'Cancel']:
            return True
        
        # Status values for controllable LNs
        if da_name == 'stVal':
            controllable_classes = ['CSWI', 'XCBR', 'XSWI', 'GGIO', 'CILO']
            return any(ln_class.startswith(cls) for cls in controllable_classes)
        
        # Settings
        if da_name in ['setMag', 'setSrc', 'minVal', 'maxVal']:
            return True
        
        return False
    
    def build_view(self):
        """Build the IEDScout flat view"""
        self.tree.clear()
        
        # Create sections in order - only 3 sections
        section_order = ['GOOSE', 'Reports', 'DataModel']
        section_colors = {
            'GOOSE': QColor(255, 240, 240),      # Light red
            'Reports': QColor(240, 255, 240),    # Light green
            'DataModel': QColor(245, 245, 245)   # Light gray
        }
        
        # Add items by section
        for section_name in section_order:
            items = self.sections.get(section_name, [])
            if not items:
                continue
            
            # Add section separator
            separator = QTreeWidgetItem(self.tree)
            separator.setText(0, f"{'='*20} {section_name} {'='*20}")
            separator.setText(4, section_name)
            separator.setBackground(0, QBrush(section_colors[section_name]))
            separator.setBackground(1, QBrush(section_colors[section_name]))
            separator.setBackground(2, QBrush(section_colors[section_name]))
            separator.setBackground(3, QBrush(section_colors[section_name]))
            separator.setBackground(4, QBrush(section_colors[section_name]))
            
            # Make separator bold
            font = separator.font(0)
            font.setBold(True)
            for col in range(5):
                separator.setFont(col, font)
            
            # Add items
            for item in items:
                tree_item = QTreeWidgetItem(self.tree)
                
                # Set data
                tree_item.setText(0, item.name)
                tree_item.setText(1, item.value)
                tree_item.setText(2, item.description)
                tree_item.setText(3, item.path)
                tree_item.setText(4, item.section)
                
                # Store item data
                tree_item.setData(0, Qt.ItemDataRole.UserRole, item)
                
                # Style based on type
                if item.editable:
                    tree_item.setBackground(1, QColor(240, 255, 240))
                
                # Special styling for sub-items
                if item.name.startswith('  ['):
                    # Indent sub-items
                    font = tree_item.font(0)
                    font.setItalic(True)
                    tree_item.setFont(0, font)
                    tree_item.setForeground(0, QBrush(QColor(80, 80, 80)))
        
        # Resize columns
        for col in range(5):
            self.tree.resizeColumnToContents(col)
    
    def clear(self):
        """Clear all data"""
        self.items.clear()
        # Only 3 sections
        self.sections = {
            'GOOSE': [],
            'Reports': [], 
            'DataModel': []
        }
        self.tree.clear()
    
    def get_item_at(self, tree_item: QTreeWidgetItem) -> Optional[IEDScoutItem]:
        """Get IEDScout item from tree item"""
        return tree_item.data(0, Qt.ItemDataRole.UserRole)
    
    def find_items_by_section(self, section: str) -> List[IEDScoutItem]:
        """Find all items in a section"""
        return self.sections.get(section, [])
    
    def find_item_by_path(self, path: str) -> Optional[IEDScoutItem]:
        """Find item by path"""
        for section_items in self.sections.values():
            for item in section_items:
                if item.path == path:
                    return item
        return None
    
    def update_item_value(self, path: str, new_value: str):
        """Update item value by path"""
        # Find in tree
        for i in range(self.tree.topLevelItemCount()):
            tree_item = self.tree.topLevelItem(i)
            item = tree_item.data(0, Qt.ItemDataRole.UserRole)
            
            if item and item.path == path:
                # Update data
                item.value = new_value
                # Update display
                tree_item.setText(1, new_value)
                tree_item.setBackground(1, QColor(255, 255, 0))  # Yellow highlight
                return True
        
        return False

# Example usage
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    # Create window
    window = QMainWindow()
    window.setWindowTitle("IEDScout View Test")
    window.resize(1200, 800)
    
    # Create tree widget
    tree = QTreeWidget()
    window.setCentralWidget(tree)
    
    # Create IEDScout manager
    manager = IEDScoutViewManager(tree)
    
    # Test data
    test_item = IEDScoutItem(
        section='GOOSE',
        name='gcb01',
        value='Enabled',
        description='GOOSE Control Block',
        path='IED1/LD0/LLN0.gcb01',
        item_type='GSEControl'
    )
    
    manager.sections['GOOSE'].append(test_item)
    
    # Build view
    manager.build_view()
    
    window.show()
    sys.exit(app.exec())