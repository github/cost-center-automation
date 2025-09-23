"""
Data Exporter for various output formats.
"""

import logging
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import pandas as pd


class DataExporter:
    """Handles exporting data to various formats."""
    
    def __init__(self, config):
        """Initialize the data exporter."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.export_dir = Path("exports")
        self.export_dir.mkdir(exist_ok=True)
        
    def export_to_csv(self, users: List[Dict], detailed: bool = False) -> str:
        """Export user data to CSV format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"copilot_users_{timestamp}.csv"
        filepath = self.export_dir / filename
        
        self.logger.info(f"Exporting {len(users)} users to CSV: {filepath}")
        
        # Prepare data for CSV
        csv_data = []
        for user in users:
            row = {
                "Username": user.get("login", ""),
                "Name": user.get("name", ""),
                "Email": user.get("email", ""),
                "Cost Center": user.get("cost_center", ""),
                "Assignment Method": user.get("assignment_method", ""),
                "User Type": user.get("type", ""),
                "Created At": user.get("created_at", ""),
                "Last Activity": user.get("last_activity_at", ""),
            }
            
            if detailed:
                row.update({
                    "User ID": user.get("id", ""),
                    "Updated At": user.get("updated_at", ""),
                    "Last Activity Editor": user.get("last_activity_editor", ""),
                    "Plan": user.get("plan", ""),
                    "Pending Cancellation": user.get("pending_cancellation_date", ""),
                })
            
            csv_data.append(row)
        
        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if csv_data:
                fieldnames = csv_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
        
        self.logger.info(f"CSV export completed: {len(csv_data)} records written")
        return str(filepath)
    
    def export_to_excel(self, users: List[Dict], detailed: bool = False) -> str:
        """Export user data to Excel format with multiple sheets."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"copilot_users_{timestamp}.xlsx"
        filepath = self.export_dir / filename
        
        self.logger.info(f"Exporting {len(users)} users to Excel: {filepath}")
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Main user data sheet
            df_users = pd.DataFrame(users)
            
            # Select and rename columns for the main sheet
            main_columns = {
                "login": "Username",
                "name": "Name", 
                "email": "Email",
                "cost_center": "Cost Center",
                "assignment_method": "Assignment Method",
                "type": "User Type",
                "created_at": "Created At",
                "last_activity_at": "Last Activity"
            }
            
            if detailed:
                main_columns.update({
                    "id": "User ID",
                    "updated_at": "Updated At",
                    "last_activity_editor": "Last Activity Editor",
                    "plan": "Plan",
                    "pending_cancellation_date": "Pending Cancellation"
                })
            
            # Filter and rename columns
            df_main = df_users[list(main_columns.keys())].rename(columns=main_columns)
            df_main.to_excel(writer, sheet_name='Users', index=False)
            
            # Cost center summary sheet
            cost_center_summary = df_users.groupby('cost_center').size().reset_index()
            cost_center_summary.columns = ['Cost Center', 'User Count']
            cost_center_summary = cost_center_summary.sort_values('User Count', ascending=False)
            cost_center_summary.to_excel(writer, sheet_name='Cost Center Summary', index=False)
            
            # Activity summary sheet if detailed
            if detailed:
                activity_df = df_users[['login', 'last_activity_at', 'last_activity_editor']].copy()
                activity_df['last_activity_at'] = pd.to_datetime(activity_df['last_activity_at'], errors='coerce')
                activity_df = activity_df.sort_values('last_activity_at', ascending=False)
                activity_df.to_excel(writer, sheet_name='Activity Summary', index=False)
        
        self.logger.info(f"Excel export completed with multiple sheets")
        return str(filepath)
    
    def export_summary(self, summary: Dict[str, int]) -> str:
        """Export cost center summary to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cost_center_summary_{timestamp}.csv"
        filepath = self.export_dir / filename
        
        self.logger.info(f"Exporting cost center summary to: {filepath}")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Cost Center', 'User Count'])
            
            for cost_center, count in summary.items():
                writer.writerow([cost_center, count])
        
        return str(filepath)
    
    def export_to_json(self, users: List[Dict], detailed: bool = False) -> str:
        """Export user data to JSON format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"copilot_users_{timestamp}.json"
        filepath = self.export_dir / filename
        
        self.logger.info(f"Exporting {len(users)} users to JSON: {filepath}")
        
        # Prepare data for JSON export
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_users": len(users),
            "users": users
        }
        
        if not detailed:
            # Remove detailed fields for non-detailed export
            simplified_users = []
            for user in users:
                simplified_user = {
                    "login": user.get("login"),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "cost_center": user.get("cost_center"),
                    "type": user.get("type"),
                    "last_activity_at": user.get("last_activity_at")
                }
                simplified_users.append(simplified_user)
            export_data["users"] = simplified_users
        
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        
        self.logger.info(f"JSON export completed")
        return str(filepath)
    
    def create_report_template(self, users: List[Dict]) -> str:
        """Create a formatted report template."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"copilot_report_{timestamp}.txt"
        filepath = self.export_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("GitHub Copilot License and Cost Center Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Users: {len(users)}\n\n")
            
            # Cost center breakdown
            cost_centers = {}
            for user in users:
                cc = user.get("cost_center", "Unassigned")
                cost_centers[cc] = cost_centers.get(cc, 0) + 1
            
            f.write("Cost Center Breakdown:\n")
            f.write("-" * 25 + "\n")
            for cc, count in sorted(cost_centers.items(), key=lambda x: x[1], reverse=True):
                f.write(f"{cc}: {count} users\n")
            
            f.write(f"\nDetailed User List:\n")
            f.write("-" * 20 + "\n")
            for user in sorted(users, key=lambda x: x.get("cost_center", "")):
                f.write(f"{user.get('login', '')} - {user.get('cost_center', 'Unassigned')}\n")
        
        return str(filepath)