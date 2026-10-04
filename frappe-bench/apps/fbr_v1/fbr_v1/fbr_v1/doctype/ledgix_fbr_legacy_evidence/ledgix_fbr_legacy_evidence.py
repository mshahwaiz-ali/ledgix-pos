import hashlib
import frappe
from fbr_v1.services.historical_document import HistoricalDocument

CONTROLLED_CAPTURE = object()

class LedgixFBRLegacyEvidence(HistoricalDocument):
    def validate(self):
        if not self.is_new() or self.flags.get("legacy_evidence_capture") is not CONTROLLED_CAPTURE:
            return super().validate()
        if hashlib.sha256(self.payload_json.encode()).hexdigest() != self.payload_hash:
            frappe.throw("Legacy evidence hash mismatch.")
    before_insert = validate
    before_save = validate

    def as_dict(self, *args, **kwargs):
        # Never serialize the preservation payload into document API responses,
        # including Administrator responses that bypass field-level permissions.
        result = super().as_dict(*args, **kwargs)
        result.pop("payload_json", None)
        return result
