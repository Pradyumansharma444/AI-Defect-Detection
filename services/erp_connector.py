import json
import os
import time
from pathlib import Path

class ERPConnector:
    """ERP Connector for exporting and synchronization of quality records with systems like SAP Business One"""
    
    def __init__(self, webhook_url="https://sap-b1-prod.company.local/api/v1/quality-sync", api_key="sap_sec_key_99182"):
        self.webhook_url = webhook_url
        self.api_key = api_key
        self.export_dir = Path(__file__).parent.parent / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.sync_logs = []
        self._log("ERP Connector initialized. Webhook Target: " + webhook_url)
        
    def _log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.sync_logs.append(f"[{timestamp}] {message}")
        if len(self.sync_logs) > 50:
            self.sync_logs.pop(0)

    def sync_detection(self, detection_id, wo_number, part_number, defect_type, is_defective, scrap_value_loss=0.0):
        """Prepares standard JSON payload and simulates posting to SAP Quality module API"""
        payload = {
            "transaction_id": f"SAP-Q-{int(time.time())}-{detection_id}",
            "inspection_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "work_order_ref": wo_number,
            "sku_id": part_number,
            "status": "REJECTED" if is_defective else "ACCEPTED",
            "defect_category": defect_type if is_defective else "N/A",
            "financial_loss_usd": scrap_value_loss,
            "disposition_required": is_defective,
            "system_source": "Antigravity AI Inspection Line 1"
        }
        
        # Simulate network post
        self._log(f"Syncing item #{detection_id} to SAP: Status={payload['status']}, Loss=${scrap_value_loss:.2f}")
        
        # Write file log
        log_file = self.export_dir / "sap_sync_ledger.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
            
        return payload

    def sync_lot_status_update(self, lot_number, status):
        """Simulates notifying ERP of lot status updates (e.g. Quarantined)"""
        payload = {
            "event": "LOT_STATUS_UPDATE",
            "lot_number": lot_number,
            "status": status,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        self._log(f"SAP ERP Webhook: Lot #{lot_number} status updated to {status}")
        
        log_file = self.export_dir / "sap_sync_ledger.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(payload) + "\n")
            
        return payload

    def get_sync_logs(self):
        return self.sync_logs
