# Plex Technologies – Asset Field Verification & FAR Reconciliation App

A lightweight web-based field data collection MVP for asset verification, physical tagging and Fixed Asset Register (FAR) reconciliation.

## Core capabilities
- Capture Asset Name, Description, Tag Number, Location, Serial Number, Model, User and Custodian.
- Record verification status, condition and field remarks.
- Search the field register.
- Import an existing FAR from CSV.
- Reconcile FAR against field data using:
  1. Tag Number
  2. Serial Number
  3. Asset Name + Location (when unique)
- Identify matched records, matched records with differences, FAR assets not found in the field, and field-only assets.
- Export the verified field register to CSV.
- Responsive interface suitable for laptops, tablets and phones.

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run: `pip install -r requirements.txt`
4. Run: `python app.py`
5. Open: `http://127.0.0.1:5000`

For LAN field deployment, run the application on a laptop/server connected to the same network and access it from tablets/phones using the server's LAN IP.

## FAR CSV import
Use a CSV with headers such as:
Asset Name, Description, Tag Number, Location, Serial Number, Model, User, Custodian

The importer also accepts common underscore variants such as `asset_name`, `tag_number`, `serial_number`, and `user_name`.

## Recommended production upgrades
- PostgreSQL/MySQL for multi-user deployment.
- User authentication and role-based permissions.
- Offline-first PWA with local storage and background synchronization.
- QR/barcode scanning using device camera.
- GPS coordinates and timestamp capture.
- Asset photographs and supporting documents.
- Project/client/site/department hierarchy.
- Audit trail for every edit.
- Excel import/export with preserved FAR columns.
- Duplicate detection and configurable reconciliation rules.
- Cloud hosting, HTTPS, backups and monitoring.
- Client-specific branding and report generation.
