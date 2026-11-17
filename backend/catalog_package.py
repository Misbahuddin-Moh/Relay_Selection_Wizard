"""Pinned inert catalog data; no vendor code or runtime downloads are loaded."""
from hashlib import sha256
import json
from pathlib import Path
from .catalog_readiness import assess_catalog

ROOT = Path(__file__).with_name('data') / 'sel_ordering_kb'


def _catalog_package():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    if type(manifest.get('contract_version')) is not int or manifest['contract_version'] != 1:
        raise ValueError('Unsupported catalog manifest version.')
    products = []
    for entry in manifest['products']:
        name = entry['file']
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('Catalog manifest contains an invalid product path.')
        product = json.loads((ROOT / name).read_text())
        products.append(assess_catalog(product, entry['model'], manifest['source_release_sha'], entry['product_sha256']))
    fingerprint = sha256(json.dumps({
        'manifest': manifest, 'products': products,
        'adapter_source': sha256(Path(__file__).with_name('catalog_readiness.py').read_bytes()).hexdigest(),
        'loader_source': sha256(Path(__file__).read_bytes()).hexdigest(),
    }, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return {'contract_version': 1, 'source_release_sha': manifest['source_release_sha'],
            'source_url': manifest['source_url'], 'fingerprint': fingerprint, 'products': products,
            'role_mapping': 'not_performed', 'complete_fit': False, 'procurement_ready': False,
            'basis': 'Version-pinned reference records only. Exact variant selection, signal-to-terminal mapping and engineering approval remain separate work.'}


def catalog_package():
    try:
        return _catalog_package()
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # Catalog evidence is optional. Corrupt/incomplete packages must not
        # become approvals or prevent existing project accounting from running.
        raw = []
        for path in sorted(ROOT.glob('*.json')):
            try:
                raw.append((path.name, sha256(path.read_bytes()).hexdigest()))
            except OSError:
                raw.append((path.name, 'unreadable'))
        fingerprint = sha256(json.dumps({'unavailable_files': raw,
            'adapter_source': sha256(Path(__file__).with_name('catalog_readiness.py').read_bytes()).hexdigest(),
            'loader_source': sha256(Path(__file__).read_bytes()).hexdigest()}, sort_keys=True).encode()).hexdigest()
        return {'contract_version': 1, 'source_release_sha': None, 'source_url': '',
                'fingerprint': fingerprint, 'products': [], 'role_mapping': 'not_performed',
                'complete_fit': False, 'procurement_ready': False,
                'basis': 'Catalog package unavailable or unsupported. Existing signal accounting remains partial; no catalog configuration can be approved.',
                'issues': [{'code': 'CATALOG_PACKAGE_UNAVAILABLE', 'message': 'Repair the versioned package and manifest before using catalog evidence.'}]}
