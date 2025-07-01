# report_generator.py
import os
import csv
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from test_executor import TestResult, TestStatus


class ReportGenerator:
    """Generate commissioning test reports"""
    
    def __init__(self):
        self.report_template = self._load_html_template()
        
    def _load_html_template(self) -> str:
        """Load HTML report template"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IEC 61850 Commissioning Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #2c3e50;
        }
        .header h1 {
            color: #2c3e50;
            margin: 0;
            font-size: 28px;
        }
        .header h2 {
            color: #7f8c8d;
            margin: 10px 0 0 0;
            font-size: 18px;
            font-weight: normal;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .info-box {
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
        }
        .info-box h3 {
            margin: 0 0 10px 0;
            color: #34495e;
            font-size: 14px;
            text-transform: uppercase;
        }
        .info-box p {
            margin: 0;
            font-size: 16px;
            color: #2c3e50;
        }
        .summary {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 4px solid #4caf50;
        }
        .summary h3 {
            margin: 0 0 15px 0;
            color: #2e7d32;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            text-align: center;
        }
        .summary-item {
            background: white;
            padding: 15px;
            border-radius: 5px;
        }
        .summary-item .value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .summary-item .label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        .pass { color: #27ae60; }
        .fail { color: #e74c3c; }
        .warning { color: #f39c12; }
        .results {
            margin-bottom: 30px;
        }
        .results h3 {
            color: #2c3e50;
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #34495e;
            color: white;
            font-weight: normal;
            text-transform: uppercase;
            font-size: 12px;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-passed {
            background: #d4edda;
            color: #155724;
        }
        .status-failed {
            background: #f8d7da;
            color: #721c24;
        }
        .status-skipped {
            background: #fff3cd;
            color: #856404;
        }
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
        .charts {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-container {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            min-height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
        }
        .test-details {
            background: #f8f9fa;
            padding: 10px;
            margin-top: 5px;
            border-radius: 3px;
            font-size: 13px;
        }
        .measurement {
            display: inline-block;
            margin-right: 15px;
            padding: 3px 8px;
            background: #e9ecef;
            border-radius: 3px;
            font-size: 12px;
        }
        @media print {
            body {
                background-color: white;
            }
            .container {
                box-shadow: none;
                padding: 0;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IEC 61850 Commissioning Test Report</h1>
            <h2>{project_name}</h2>
        </div>
        
        <div class="info-grid">
            <div class="info-box">
                <h3>Test Information</h3>
                <p><strong>Date:</strong> {test_date}</p>
                <p><strong>Time:</strong> {test_time}</p>
                <p><strong>Duration:</strong> {test_duration}</p>
                <p><strong>Operator:</strong> {operator}</p>
            </div>
            <div class="info-box">
                <h3>System Information</h3>
                <p><strong>Station:</strong> {station_name}</p>
                <p><strong>IEDs Tested:</strong> {ied_count}</p>
                <p><strong>Test Mode:</strong> {test_mode}</p>
                <p><strong>Safety Checks:</strong> {safety_status}</p>
            </div>
        </div>
        
        <div class="summary">
            <h3>Test Summary</h3>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="value">{total_tests}</div>
                    <div class="label">Total Tests</div>
                </div>
                <div class="summary-item">
                    <div class="value pass">{passed_tests}</div>
                    <div class="label">Passed</div>
                </div>
                <div class="summary-item">
                    <div class="value fail">{failed_tests}</div>
                    <div class="label">Failed</div>
                </div>
                <div class="summary-item">
                    <div class="value">{pass_rate}%</div>
                    <div class="label">Pass Rate</div>
                </div>
            </div>
        </div>
        
        <div class="results">
            <h3>Detailed Test Results</h3>
            {results_table}
        </div>
        
        <div class="charts">
            <div class="chart-container">
                <canvas id="statusChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="performanceChart"></canvas>
            </div>
        </div>
        
        <div class="results">
            <h3>Test Details by IED</h3>
            {ied_details}
        </div>
        
        <div class="footer">
            <p>Generated by IEC 61850 Commissioning System v1.0</p>
            <p>{timestamp}</p>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // Status Chart
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: ['Passed', 'Failed', 'Skipped', 'Error'],
                datasets: [{
                    data: [{passed_tests}, {failed_tests}, {skipped_tests}, {error_tests}],
                    backgroundColor: ['#27ae60', '#e74c3c', '#f39c12', '#c0392b']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Test Status Distribution'
                    }
                }
            }
        });
        
        // Performance Chart
        const perfCtx = document.getElementById('performanceChart').getContext('2d');
        new Chart(perfCtx, {
            type: 'bar',
            data: {
                labels: {test_categories},
                datasets: [{
                    label: 'Average Duration (seconds)',
                    data: {category_durations},
                    backgroundColor: '#3498db'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Test Performance by Category'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    </script>
</body>
</html>
"""
        
    def generate_html_report(self, test_results: List[TestResult],
                           scl_data: Optional[Dict] = None,
                           connections: Optional[Dict] = None) -> str:
        """Generate HTML report"""
        
        # Calculate summary statistics
        summary = self._calculate_summary(test_results)
        
        # Generate results table
        results_table = self._generate_results_table(test_results)
        
        # Generate IED details
        ied_details = self._generate_ied_details(test_results)
        
        # Get test categories and durations
        categories, durations = self._get_category_statistics(test_results)
        
        # Fill template
        html_content = self.report_template.format(
            project_name=scl_data.get('project_name', 'IEC 61850 Commissioning') if scl_data else 'IEC 61850 Commissioning',
            test_date=datetime.now().strftime('%Y-%m-%d'),
            test_time=datetime.now().strftime('%H:%M:%S'),
            test_duration=self._format_duration(summary['total_duration']),
            operator='System Operator',
            station_name=scl_data.get('station_name', 'Substation') if scl_data else 'Substation',
            ied_count=len(set(r.ied_name for r in test_results)),
            test_mode='Simulation' if any(r.details and 'simulation' in r.details.lower() for r in test_results) else 'Live',
            safety_status='Enabled',
            total_tests=summary['total'],
            passed_tests=summary['passed'],
            failed_tests=summary['failed'],
            skipped_tests=summary['skipped'],
            error_tests=summary['error'],
            pass_rate=summary['pass_rate'],
            results_table=results_table,
            ied_details=ied_details,
            test_categories=json.dumps(categories),
            category_durations=json.dumps(durations),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        return html_content
        
    def generate_csv_report(self, test_results: List[TestResult], filename: str):
        """Generate CSV report"""
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'test_id', 'test_name', 'ied_name', 'status',
                'start_time', 'end_time', 'duration', 'details',
                'error_message', 'measurements'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in test_results:
                writer.writerow({
                    'test_id': result.test_id,
                    'test_name': result.test_name,
                    'ied_name': result.ied_name,
                    'status': result.status.value,
                    'start_time': datetime.fromtimestamp(result.start_time).strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': datetime.fromtimestamp(result.end_time).strftime('%Y-%m-%d %H:%M:%S') if result.end_time else '',
                    'duration': f"{result.duration:.2f}",
                    'details': result.details or '',
                    'error_message': result.error_message or '',
                    'measurements': json.dumps(result.measurements) if result.measurements else ''
                })
                
    def generate_json_report(self, test_results: List[TestResult], filename: str):
        """Generate JSON report"""
        
        report_data = {
            'report_info': {
                'generated_at': datetime.now().isoformat(),
                'version': '1.0',
                'total_tests': len(test_results)
            },
            'summary': self._calculate_summary(test_results),
            'results': []
        }
        
        for result in test_results:
            report_data['results'].append({
                'test_id': result.test_id,
                'test_name': result.test_name,
                'ied_name': result.ied_name,
                'status': result.status.value,
                'start_time': result.start_time,
                'end_time': result.end_time,
                'duration': result.duration,
                'details': result.details,
                'error_message': result.error_message,
                'measurements': result.measurements,
                'timestamp': result.timestamp
            })
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
            
    def _calculate_summary(self, test_results: List[TestResult]) -> Dict:
        """Calculate summary statistics"""
        
        total = len(test_results)
        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in test_results if r.status == TestStatus.SKIPPED)
        error = sum(1 for r in test_results if r.status == TestStatus.ERROR)
        
        total_duration = sum(r.duration for r in test_results if r.duration)
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'error': error,
            'pass_rate': round((passed / total * 100) if total > 0 else 0, 1),
            'total_duration': total_duration
        }
        
    def _generate_results_table(self, test_results: List[TestResult]) -> str:
        """Generate HTML table of results"""
        
        if not test_results:
            return "<p>No test results available.</p>"
            
        table_html = """
        <table>
            <thead>
                <tr>
                    <th>Test ID</th>
                    <th>Test Name</th>
                    <th>IED</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Details</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for result in test_results:
            status_class = f"status-{result.status.value.lower()}"
            duration_str = f"{result.duration:.2f}s" if result.duration else "--"
            timestamp_str = datetime.fromtimestamp(result.timestamp).strftime('%H:%M:%S')
            
            details = result.details or result.error_message or "--"
            if len(details) > 100:
                details = details[:100] + "..."
                
            table_html += f"""
                <tr>
                    <td>{result.test_id}</td>
                    <td>{result.test_name}</td>
                    <td>{result.ied_name}</td>
                    <td><span class="status-badge {status_class}">{result.status.value}</span></td>
                    <td>{duration_str}</td>
                    <td>{details}</td>
                    <td>{timestamp_str}</td>
                </tr>
            """
            
            # Add measurements if available
            if result.measurements:
                measurements_html = "<div class='test-details'>"
                for key, value in result.measurements.items():
                    if isinstance(value, (int, float)):
                        measurements_html += f"<span class='measurement'>{key}: {value:.2f}</span>"
                measurements_html += "</div>"
                
                table_html += f"""
                <tr>
                    <td colspan="7">{measurements_html}</td>
                </tr>
                """
                
        table_html += """
            </tbody>
        </table>
        """
        
        return table_html
        
    def _generate_ied_details(self, test_results: List[TestResult]) -> str:
        """Generate detailed results by IED"""
        
        # Group by IED
        ied_results = {}
        for result in test_results:
            if result.ied_name not in ied_results:
                ied_results[result.ied_name] = []
            ied_results[result.ied_name].append(result)
            
        html = ""
        
        for ied_name, results in ied_results.items():
            # Calculate IED-specific summary
            total = len(results)
            passed = sum(1 for r in results if r.status == TestStatus.PASSED)
            failed = sum(1 for r in results if r.status == TestStatus.FAILED)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            html += f"""
            <div class="info-box" style="margin-bottom: 20px;">
                <h3>{ied_name}</h3>
                <p>Total Tests: {total} | Passed: {passed} | Failed: {failed} | Pass Rate: {pass_rate:.1f}%</p>
            </div>
            """
            
        return html
        
    def _get_category_statistics(self, test_results: List[TestResult]) -> tuple[List[str], List[float]]:
        """Get test categories and average durations"""
        
        category_map = {
            'connectivity': 'Basic',
            'time_sync': 'Basic',
            'data_model': 'Basic',
            'xcbr_control': 'Control',
            'xswi_control': 'Control',
            'cswi_control': 'Control',
            'ptoc_test': 'Protection',
            'pdif_test': 'Protection',
            'ptov_test': 'Protection',
            'ptuv_test': 'Protection',
            'mmxu_verify': 'Measurement',
            'msqi_test': 'Measurement',
            'goose_publish': 'GOOSE',
            'goose_subscribe': 'GOOSE',
            'goose_performance': 'GOOSE',
            'interlock_basic': 'Interlocking',
            'interlock_complex': 'Interlocking',
            'response_time': 'Performance',
            'throughput': 'Performance'
        }
        
        category_durations = {}
        category_counts = {}
        
        for result in test_results:
            category = category_map.get(result.test_id, 'Other')
            
            if category not in category_durations:
                category_durations[category] = 0
                category_counts[category] = 0
                
            if result.duration:
                category_durations[category] += result.duration
                category_counts[category] += 1
                
        # Calculate averages
        categories = []
        durations = []
        
        for category in sorted(category_durations.keys()):
            categories.append(category)
            if category_counts[category] > 0:
                avg_duration = category_durations[category] / category_counts[category]
                durations.append(round(avg_duration, 2))
            else:
                durations.append(0)
                
        return categories, durations
        
    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string"""
        
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"