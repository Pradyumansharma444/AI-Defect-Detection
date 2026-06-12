import sqlite3
from datetime import datetime
import hashlib
import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Optional


class DefectDatabase:
    """Database for storing defect detection results, SPC tracking, audit trails, and ERP/MES quality records"""
    
    def __init__(self, db_path='defect_detection.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                model_type TEXT,
                is_defective BOOLEAN,
                defect_type TEXT,
                confidence REAL,
                severity TEXT,
                num_defects INTEGER,
                processing_time_ms REAL,
                metadata TEXT,
                operator_override TEXT,
                flagged_for_retraining BOOLEAN DEFAULT FALSE,
                lot_number TEXT
            );
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_number TEXT UNIQUE,
                start_time DATETIME,
                end_time DATETIME,
                total_products INTEGER,
                defective_count INTEGER DEFAULT 0,
                defect_rate REAL DEFAULT 0,
                status TEXT DEFAULT 'in_progress'
            );
            CREATE TABLE IF NOT EXISTS quality_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                hour INTEGER,
                total_inspected INTEGER,
                total_defects INTEGER,
                defect_rate REAL,
                avg_confidence REAL,
                critical_defects INTEGER,
                major_defects INTEGER,
                minor_defects INTEGER,
                model_name TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                detection_id INTEGER,
                acknowledged BOOLEAN DEFAULT FALSE,
                acknowledged_by TEXT,
                acknowledged_at DATETIME,
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            );
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                date DATE,
                total_predictions INTEGER,
                avg_inference_time_ms REAL,
                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL
            );
            
            -- ERP/MES Quality Tables
            CREATE TABLE IF NOT EXISTS work_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wo_number TEXT UNIQUE,
                product_name TEXT,
                quantity_target INTEGER,
                quantity_produced INTEGER DEFAULT 0,
                quantity_defective INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, active, completed, halted
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            );
            CREATE TABLE IF NOT EXISTS maintenance_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                defect_type TEXT,
                source_detection_id INTEGER,
                assigned_technician TEXT,
                description TEXT,
                status TEXT DEFAULT 'open', -- open, in_progress, resolved
                resolved_at DATETIME,
                resolution_notes TEXT,
                FOREIGN KEY (source_detection_id) REFERENCES detections(id)
            );
            CREATE TABLE IF NOT EXISTS inventory_scrap (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                product_name TEXT,
                defect_type TEXT,
                scrap_value_loss REAL DEFAULT 0.0,
                disposition TEXT DEFAULT 'quarantined', -- quarantined, scrapped, reworked, released
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            );
            CREATE TABLE IF NOT EXISTS operator_shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_name TEXT,
                shift_name TEXT, -- Morning, Evening, Night
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                inspected_count INTEGER DEFAULT 0,
                defective_count INTEGER DEFAULT 0
            );
            
            -- --- Traceability & Lot Tracking ---
            CREATE TABLE IF NOT EXISTS lot_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lot_number TEXT UNIQUE,
                supplier_name TEXT,
                raw_material_batch TEXT,
                machine_id TEXT,
                status TEXT DEFAULT 'approved', -- approved, quarantined, flagged_for_reinspection
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            
            -- --- Statistical Process Control (SPC) ---
            CREATE TABLE IF NOT EXISTS spc_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                rule_violated TEXT, -- Western Electric Rule identifier
                metric_name TEXT, -- e.g. Anomaly Score
                value REAL,
                ucl REAL,
                lcl REAL
            );
            
            -- --- Defect Severity SKUs & Zoning ---
            CREATE TABLE IF NOT EXISTS skus_defect_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id TEXT UNIQUE,
                name TEXT,
                max_scratch_length REAL DEFAULT 5.0,
                max_dent_area REAL DEFAULT 100.0,
                zone_a_multiplier REAL DEFAULT 2.0, -- visible/critical zone multiplier
                zone_b_multiplier REAL DEFAULT 0.5  -- hidden zone multiplier
            );
            
            -- --- Operator Verification (HITL) ---
            CREATE TABLE IF NOT EXISTS detection_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                verification_status TEXT, -- confirmed_defect, false_positive, reinspect
                operator_username TEXT,
                verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                electronic_signature TEXT,
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            );
            
            -- --- Process Parameters (RCA) ---
            CREATE TABLE IF NOT EXISTS process_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                temperature REAL, -- Celsius
                vibration REAL, -- mm/s
                line_speed REAL, -- m/s
                FOREIGN KEY (detection_id) REFERENCES detections(id)
            );
            
            -- --- Compliance Immutable Audit Log (21 CFR Part 11) ---
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                username TEXT,
                action TEXT,
                record_hash TEXT -- SHA-256 cryptographic chain hash
            );
            
            CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp);
            CREATE INDEX IF NOT EXISTS idx_detections_defect_type ON detections(defect_type);
            CREATE INDEX IF NOT EXISTS idx_quality_stats_date ON quality_stats(date);
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);
            CREATE INDEX IF NOT EXISTS idx_maintenance_tickets_status ON maintenance_tickets(status);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
        ''')
        
        # Schema Migrations: Alter table to add operator_override, flagged_for_retraining, and lot_number columns if missing
        try:
            self.cursor.execute("SELECT operator_override FROM detections LIMIT 1")
        except sqlite3.OperationalError:
            try:
                self.cursor.execute("ALTER TABLE detections ADD COLUMN operator_override TEXT")
                self.cursor.execute("ALTER TABLE detections ADD COLUMN flagged_for_retraining BOOLEAN DEFAULT FALSE")
                self.cursor.execute("ALTER TABLE detections ADD COLUMN lot_number TEXT")
                self.conn.commit()
                print("✓ Migrated database schema with operator_override & lot columns successfully")
            except Exception as ex:
                print(f"Error migrating database table: {ex}")
                
        # Ensure default SKUs exist
        self.cursor.execute("INSERT OR IGNORE INTO skus_defect_criteria (sku_id, name, max_scratch_length, max_dent_area) VALUES (?, ?, ?, ?)",
                            ("SKU-001", "Precision Engine Block", 3.0, 80.0))
        self.cursor.execute("INSERT OR IGNORE INTO skus_defect_criteria (sku_id, name, max_scratch_length, max_dent_area) VALUES (?, ?, ?, ?)",
                            ("SKU-002", "Piston Ring Outer Ring", 6.0, 150.0))
        self.conn.commit()
    
    def insert_detection(self, detection_result: Dict):
        query = '''
            INSERT INTO detections (
                image_path, model_type, is_defective, defect_type,
                confidence, severity, num_defects, processing_time_ms, metadata, lot_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (
            detection_result.get('image_path'),
            detection_result.get('model_type', 'default'),
            detection_result.get('is_defective', False),
            detection_result.get('defect_type'),
            detection_result.get('confidence'),
            detection_result.get('severity', {}).get('level') if isinstance(detection_result.get('severity'), dict) else detection_result.get('severity'),
            detection_result.get('num_defects', 0),
            detection_result.get('processing_time_ms', 0),
            json.dumps(detection_result.get('metadata', {})),
            detection_result.get('lot_number')
        ))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def create_alert(self, detection_id: int, alert_type: str, severity: str, message: str):
        query = '''
            INSERT INTO alerts (detection_id, alert_type, severity, message)
            VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (detection_id, alert_type, severity, message))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_recent_detections(self, limit=100, is_defective=None, defect_type=None):
        query = "SELECT * FROM detections WHERE 1=1"
        params = []
        if is_defective is not None:
            query += " AND is_defective = ?"
            params.append(is_defective)
        if defect_type:
            query += " AND defect_type = ?"
            params.append(defect_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        self.cursor.execute(query, params)
        columns = [description[0] for description in self.cursor.description]
        results = self.cursor.fetchall()
        return [dict(zip(columns, row)) for row in results]
    
    def get_statistics(self, start_date=None, end_date=None):
        query = '''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_inspected,
                SUM(CASE WHEN is_defective THEN 1 ELSE 0 END) as total_defects,
                ROUND(AVG(confidence), 3) as avg_confidence,
                SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) as critical_defects,
                SUM(CASE WHEN severity = 'Major' THEN 1 ELSE 0 END) as major_defects,
                SUM(CASE WHEN severity = 'Minor' THEN 1 ELSE 0 END) as minor_defects
            FROM detections
        '''
        params = []
        if start_date and end_date:
            query += " WHERE timestamp BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        query += " GROUP BY DATE(timestamp) ORDER BY date"
        self.cursor.execute(query, params)
        columns = [description[0] for description in self.cursor.description]
        results = self.cursor.fetchall()
        stats = [dict(zip(columns, row)) for row in results]
        for stat in stats:
            stat['defect_rate'] = round(
                (stat['total_defects'] / stat['total_inspected'] * 100) if stat['total_inspected'] > 0 else 0, 
                2
            )
        return stats
    
    # --- ERP / MES Quality Methods ---
    
    def create_work_order(self, wo_number: str, product_name: str, quantity_target: int):
        try:
            query = '''
                INSERT INTO work_orders (wo_number, product_name, quantity_target)
                VALUES (?, ?, ?)
            '''
            self.cursor.execute(query, (wo_number, product_name, quantity_target))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            self.cursor.execute("SELECT id FROM work_orders WHERE wo_number = ?", (wo_number,))
            res = self.cursor.fetchone()
            return res[0] if res else None

    def get_all_work_orders(self):
        self.cursor.execute("SELECT * FROM work_orders ORDER BY created_at DESC")
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def get_active_work_order(self):
        self.cursor.execute("SELECT * FROM work_orders WHERE status = 'active' LIMIT 1")
        columns = [d[0] for d in self.cursor.description]
        row = self.cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    def set_work_order_status(self, wo_id: int, status: str):
        completed_at = datetime.now() if status == 'completed' else None
        if status == 'active':
            self.cursor.execute("UPDATE work_orders SET status = 'halted' WHERE status = 'active'")
        query = "UPDATE work_orders SET status = ?, completed_at = ? WHERE id = ?"
        self.cursor.execute(query, (status, completed_at, wo_id))
        self.conn.commit()

    def update_work_order_yield(self, wo_id: int, increment_produced=1, increment_defective=0):
        query = '''
            UPDATE work_orders 
            SET quantity_produced = quantity_produced + ?, 
                quantity_defective = quantity_defective + ?
            WHERE id = ?
        '''
        self.cursor.execute(query, (increment_produced, increment_defective, wo_id))
        self.conn.commit()

    def create_maintenance_ticket(self, defect_type: str, source_detection_id: int, assigned_technician: str, description: str):
        ticket_number = f"MT-{int(datetime.now().timestamp())}"
        query = '''
            INSERT INTO maintenance_tickets (ticket_number, defect_type, source_detection_id, assigned_technician, description)
            VALUES (?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (ticket_number, defect_type, source_detection_id, assigned_technician, description))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_active_tickets(self):
        query = "SELECT * FROM maintenance_tickets WHERE status != 'resolved' ORDER BY created_at DESC"
        self.cursor.execute(query)
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def resolve_ticket(self, ticket_id: int, resolution_notes: str):
        query = '''
            UPDATE maintenance_tickets 
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, resolution_notes = ?
            WHERE id = ?
        '''
        self.cursor.execute(query, (resolution_notes, ticket_id))
        self.conn.commit()

    def log_scrap_item(self, detection_id: int, product_name: str, defect_type: str, scrap_value_loss: float):
        query = '''
            INSERT INTO inventory_scrap (detection_id, product_name, defect_type, scrap_value_loss)
            VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (detection_id, product_name, defect_type, scrap_value_loss))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_scrap_ledger(self, limit=100):
        query = "SELECT * FROM inventory_scrap ORDER BY updated_at DESC LIMIT ?"
        self.cursor.execute(query, (limit,))
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def update_scrap_disposition(self, scrap_id: int, disposition: str):
        query = '''
            UPDATE inventory_scrap 
            SET disposition = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
        self.cursor.execute(query, (disposition, scrap_id))
        self.conn.commit()

    def get_operator_stats(self):
        query = "SELECT * FROM operator_shifts ORDER BY start_time DESC"
        self.cursor.execute(query)
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        
    def start_operator_shift(self, operator_name: str, shift_name: str):
        self.cursor.execute("UPDATE operator_shifts SET end_time = CURRENT_TIMESTAMP WHERE end_time IS NULL")
        query = '''
            INSERT INTO operator_shifts (operator_name, shift_name)
            VALUES (?, ?)
        '''
        self.cursor.execute(query, (operator_name, shift_name))
        self.conn.commit()
        return self.cursor.lastrowid

    def update_active_shift_stats(self, increment_inspected=1, increment_defective=0):
        query = '''
            UPDATE operator_shifts
            SET inspected_count = inspected_count + ?,
                defective_count = defective_count + ?
            WHERE end_time IS NULL
        '''
        self.cursor.execute(query, (increment_inspected, increment_defective))
        self.conn.commit()

    # --- Traceability & Lot Tracking Methods ---
    
    def log_lot_batch(self, lot_number: str, supplier_name: str, raw_material_batch: str, machine_id: str):
        try:
            query = '''
                INSERT INTO lot_batches (lot_number, supplier_name, raw_material_batch, machine_id)
                VALUES (?, ?, ?, ?)
            '''
            self.cursor.execute(query, (lot_number, supplier_name, raw_material_batch, machine_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            self.cursor.execute("SELECT id FROM lot_batches WHERE lot_number = ?", (lot_number,))
            res = self.cursor.fetchone()
            return res[0] if res else None

    def get_all_lots(self):
        self.cursor.execute("SELECT * FROM lot_batches ORDER BY created_at DESC")
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def set_lot_status(self, lot_number: str, status: str):
        self.cursor.execute("UPDATE lot_batches SET status = ? WHERE lot_number = ?", (status, lot_number))
        self.conn.commit()

    # --- Statistical Process Control (SPC) Western Electric Rules ---

    def check_spc_rules(self, metric_name='Anomaly Score'):
        # Western Electric Rule 1: Point outside 3-Sigma limits (UCL/LCL)
        # Fetch last 30 scans where is_defective is false to establish process parameters
        self.cursor.execute("SELECT metadata FROM detections ORDER BY timestamp DESC LIMIT 30")
        rows = self.cursor.fetchall()
        scores = []
        for r in rows:
            try:
                meta = json.loads(r[0])
                if 'anomaly_score' in meta:
                    scores.append(meta['anomaly_score'])
            except Exception:
                pass
                
        if len(scores) < 10:
            return  # Need baseline history to establish mean/deviation
            
        mean = np.mean(scores)
        std = np.std(scores) if np.std(scores) > 0 else 0.05
        ucl = mean + 3 * std
        lcl = max(0, mean - 3 * std)
        
        # Check the very last scan score
        last_score = scores[0]
        
        # Rule 1: Out of Control
        if last_score > ucl:
            rule_text = "Western Electric Rule 1: Anomaly Score exceeds Upper Control Limit (+3 Sigma)"
            self.cursor.execute("INSERT INTO spc_alerts (rule_violated, metric_name, value, ucl, lcl) VALUES (?, ?, ?, ?, ?)",
                                (rule_text, metric_name, last_score, ucl, lcl))
            self.conn.commit()
            
        # Rule 2: 8 consecutive points on same side of the mean
        if len(scores) >= 8:
            last_8 = scores[:8]
            if all(s > mean for s in last_8) or all(s < mean for s in last_8):
                rule_text = "Western Electric Rule 2: 8 consecutive points on the same side of the process mean"
                self.cursor.execute("INSERT INTO spc_alerts (rule_violated, metric_name, value, ucl, lcl) VALUES (?, ?, ?, ?, ?)",
                                    (rule_text, metric_name, last_score, ucl, lcl))
                self.conn.commit()

    def get_spc_alerts(self, limit=10):
        self.cursor.execute("SELECT * FROM spc_alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    # --- SKU Defect Specification Limits ---
    
    def get_sku_criteria(self, sku_id: str):
        self.cursor.execute("SELECT * FROM skus_defect_criteria WHERE sku_id = ?", (sku_id,))
        columns = [d[0] for d in self.cursor.description]
        row = self.cursor.fetchone()
        if row:
            return dict(zip(columns, row))
        else:
            return {'sku_id': sku_id, 'max_scratch_length': 5.0, 'max_dent_area': 100.0, 'zone_a_multiplier': 2.0, 'zone_b_multiplier': 0.5}

    # --- Operator Verification (HITL) ---

    def create_verification(self, detection_id: int, status: str, username: str, signature: str):
        query = '''
            INSERT INTO detection_verifications (detection_id, verification_status, operator_username, electronic_signature)
            VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (detection_id, status, username, signature))
        self.conn.commit()
        return self.cursor.lastrowid

    # --- Process Parameters (RCA) ---
    
    def log_process_parameters(self, detection_id: int, temperature: float, vibration: float, line_speed: float):
        query = '''
            INSERT INTO process_parameters (detection_id, temperature, vibration, line_speed)
            VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (detection_id, temperature, vibration, line_speed))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_rca_correlation_dataset(self):
        query = '''
            SELECT d.is_defective, d.defect_type, p.temperature, p.vibration, p.line_speed
            FROM detections d
            JOIN process_parameters p ON d.id = p.detection_id
            ORDER BY d.timestamp DESC LIMIT 100
        '''
        self.cursor.execute(query)
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    # --- Compliance Immutable Audit Log (21 CFR Part 11) ---
    
    def insert_audit_log(self, username: str, action: str):
        # Fetch the previous record's hash to form a cryptographic chain
        self.cursor.execute("SELECT record_hash FROM audit_logs ORDER BY id DESC LIMIT 1")
        res = self.cursor.fetchone()
        prev_hash = res[0] if res else "genesis_block_defect_inspection"
        
        timestamp = datetime.now().isoformat()
        
        # Compute SHA-256 chain hash
        hash_input = f"{prev_hash}|{timestamp}|{username}|{action}"
        record_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        query = '''
            INSERT INTO audit_logs (timestamp, username, action, record_hash)
            VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (timestamp, username, action, record_hash))
        self.conn.commit()
        return record_hash

    def get_audit_trail(self, limit=100):
        self.cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    # --- HITL Continuous Learning Override ---

    def override_detection_label(self, detection_id: int, override_label: str):
        is_defective = 0 if override_label == 'good' else 1
        query = '''
            UPDATE detections 
            SET operator_override = ?, 
                flagged_for_retraining = 1,
                is_defective = ?,
                defect_type = ?
            WHERE id = ?
        '''
        self.cursor.execute(query, (override_label, is_defective, override_label, detection_id))
        self.conn.commit()
        
        if override_label == 'good':
            self.cursor.execute("DELETE FROM inventory_scrap WHERE detection_id = ?", (detection_id,))
            self.cursor.execute("DELETE FROM alerts WHERE detection_id = ?", (detection_id,))
            self.conn.commit()

    def get_retraining_queue(self):
        query = "SELECT * FROM detections WHERE flagged_for_retraining = 1 ORDER BY timestamp DESC"
        self.cursor.execute(query)
        columns = [d[0] for d in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def clear_retraining_queue(self):
        self.cursor.execute("UPDATE detections SET flagged_for_retraining = 0")
        self.conn.commit()

    def export_to_csv(self, table_name, output_path):
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, self.conn)
        df.to_csv(output_path, index=False)
        return output_path
    
    def cleanup_old_records(self, days=90):
        query = "DELETE FROM detections WHERE timestamp < datetime('now', ?)"
        self.cursor.execute(query, (f'-{days} days',))
        self.conn.commit()
        deleted = self.cursor.rowcount
        print(f"Cleaned up {deleted} old records")
        return deleted
    
    def close(self):
        if self.conn:
            self.conn.close()
