#!/usr/bin/env python3
"""Source-only gate for current Federal V1 and non-executable historical DI."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / 'frappe-bench/apps'
V1 = APPS / 'fbr_v1/fbr_v1'
LED = APPS / 'ledgix_saas'
DI = APPS / 'fbr_v12/fbr_v12'

def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)

for app in (V1, LED, DI):
    for path in app.rglob('*.py'):
        if path.name.startswith('test_'):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                require(not any(marker in node.value for marker in ('di_data/v1', '/pdi/v', '/dist/v', 'validateinvoicedata', 'postinvoicedata')), f'DI endpoint: {path}')
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or '']
                if app != DI:
                    require(not any(n.startswith('fbr_v12') for n in names), f'active DI import: {path}')
                if path != V1 / 'protocol/transport.py':
                    require(not any(n.split('.')[0] in ('requests', 'httpx') or n in ('http.client', 'urllib.request') for n in names), f'alternate HTTP import: {path}')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'requests' and node.func.attr in ('get','post','request'):
                    require(path == V1 / 'protocol/transport.py', f'alternate HTTP call: {path}')

hooks = ast.parse((DI / 'hooks.py').read_text())
values = {n.targets[0].id: ast.literal_eval(n.value) for n in hooks.body if isinstance(n, ast.Assign)}
require(values.get('before_install') == 'fbr_v12.retired.reject', 'new DI installation must fail')
require(not values.get('doc_events') and not values.get('scheduler_events'), 'active DI hooks')
for forbidden in ('after_install','after_migrate','app_include_js','jinja','erpnext_taxable_base_resolvers'):
    require(forbidden not in values, 'DI runtime hook ' + forbidden)
require(not list(DI.rglob('*.json')), 'DI standard/runtime JSON remains')
for path in DI.rglob('*.py'):
    if path.name in ('__init__.py','hooks.py','retired.py'):
        continue
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            require(len(node.body) == 1 and isinstance(node.body[0], ast.Return) and isinstance(node.body[0].value, ast.Call) and isinstance(node.body[0].value.func, ast.Name) and node.body[0].value.func.id == 'reject', f'executable DI function: {path}:{node.name}')
        if isinstance(node, ast.ClassDef):
            require([ast.unparse(base) for base in node.bases] == ['HistoricalDocument'] and all(isinstance(n, ast.Pass) for n in node.body), f'executable DI controller: {path}')
for suffix in ('business_nature','reference_data','sandbox_certification','sandbox_scenario'):
    name = 'ledgix_fbr_' + suffix
    path = V1 / 'fbr_v1/doctype' / name
    require(not (path / (name + '.json')).exists(), 'fresh retired JSON: ' + name)
    require((path / (name + '.py')).exists(), 'historical controller missing: ' + name)
profile = json.loads((V1 / 'fbr_v1/doctype/ledgix_fbr_integration_profile/ledgix_fbr_integration_profile.json').read_text())
fields = {f['fieldname'] for f in profile['fields']}
require(not fields.intersection({'business_natures','sector','onboarding_status','sandbox_token','production_token','block_sale_if_fbr_fails','offline_upload_window_hours','reference_sync_status','last_reference_sync_at','reference_version','activation_reference','activation_evidence'}), 'DI-only current profile authority')
release = (LED / 'api/release_acceptance.py').read_text()
require('sandbox_certification_complete' not in release and 'fbr_external_certification_complete' not in release, 'wrong release Sandbox/approval semantics')
for name in ('fbr_sandbox_transport_acceptance_complete','fbr_external_production_approval_complete','fbr_production_configuration_ready','fbr_production_release_ready'):
    require(name in release, 'release gate missing: ' + name)
for file in ('api/fbr_payload.py','api/printing.py','patches/v1_0/backfill_sale_seller_snapshots.py','patches/v1_0/backfill_sale_item_identity_and_sync_receipts.py'):
    source = (LED / file).read_text()
    for forbidden in ('get_seller_identity','get_customer_for_fbr(sale_doc','get_brand_settings','resolve_invoice_identity','erpnext_live','"Ledgix Item"'):
        require(forbidden not in source, 'live historical reconstruction: ' + file)
for name in ('ledgix_b2b_invoice','ledgix_thermal_receipt'):
    html = json.loads((LED / 'ledgix/print_format' / name / (name + '.json')).read_text())['html']
    for forbidden in ('get_doc','Brand Settings','fbr_invoice_number','get_fbr_qr_data_uri','immutable'):
        require(forbidden not in html, 'unverified archival fiscal claim: ' + name)
for base in ('scripts','deploy'):
    for path in (ROOT / base).rglob('*.sh'):
        if 'archive' in path.parts:
            continue
        import re
        require(not re.search(r'install-app\s+fbr_v12', path.read_text()), 'current DI installation script: ' + str(path))
require('"fbr_v12"' not in (ROOT / 'scripts/validation/validate_repo.sh').read_text(), 'DI app in current validation')
print('PASS: Federal V1-only architecture; DI endpoints=0; alternate HTTP=0; historical live fallback=0; wrong Sandbox/approval equivalence=0')
