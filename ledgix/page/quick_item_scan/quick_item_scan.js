// ============================================================
// QUICK ITEM ENTRY PAGE
// ============================================================

frappe.pages['quick-item-scan'].on_page_load = function(wrapper) {

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "",
		single_column: true
	});
	page.set_title("");

	const $page_container = $(wrapper).closest(".page-container");
	$page_container.addClass("ledgix-page-no-frappe-head");

	$page_container
		.find(".page-head, .page-head-content, .page-title, .title-area, .page-actions")
		.hide();

	let lookupTimer = null;
	let lastLookupCode = "";
	let lastLookupResult = null;
	let html5QrCode = null;
	let cameraRunning = false;

	$(page.body).html(`
		<div class="lx-quick-scan-page" style="max-width: 820px; margin: 36px auto; padding: 0 14px;">

			<div style="
				padding: 32px;
				border: 1px solid #e5e7eb;
				border-radius: 26px;
				background: #ffffff;
				box-shadow: 0 18px 45px rgba(15, 23, 42, 0.07);
			">

				<div style="margin-bottom: 24px;">
					<h2 style="margin: 0 0 8px; font-size: 28px; font-weight: 800;">
						Quick Item Entry
					</h2>

					<p style="color: #6b7280; margin: 0; font-size: 14px;">
						Scan or type a barcode, SKU, or item code. Ledgix will instantly detect whether the item already exists.
					</p>
				</div>

				<div style="
					padding: 18px;
					border-radius: 20px;
					background: #f9fafb;
					border: 1px solid #e5e7eb;
				">

					<label style="
						display: block;
						margin-bottom: 8px;
						font-size: 13px;
						font-weight: 700;
						color: #374151;
					">
						Barcode / SKU / Item Code
					</label>

					<input
						id="ledgix-scan-code"
						type="text"
						placeholder="Scan barcode or type code here"
						style="
							width: 100%;
							padding: 16px 18px;
							font-size: 18px;
							border: 1px solid #d1d5db;
							border-radius: 16px;
							outline: none;
							background: #ffffff;
						"
						autofocus
					/>

					<div id="ledgix-live-status" style="
						margin-top: 12px;
						font-size: 14px;
						color: #6b7280;
					">
						Ready for scanner input.
					</div>

				</div>

				<div style="display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap;">

					<button class="btn btn-primary" id="ledgix-continue-btn">
						Continue
					</button>

					<button class="btn btn-default" id="ledgix-camera-btn">
						Camera Scan
					</button>

					<button class="btn btn-default" id="ledgix-clear-btn">
						Clear
					</button>

				</div>

				<div id="ledgix-camera-area" style="
					display: none;
					margin-top: 22px;
					padding: 16px;
					border-radius: 18px;
					background: #f9fafb;
					border: 1px dashed #d1d5db;
				">
					<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
						<strong>Camera Scanner</strong>
						<button class="btn btn-xs btn-default" id="ledgix-stop-camera-btn">
							Close
						</button>
					</div>

					<div id="ledgix-camera-reader" style="width: 100%;"></div>
				</div>

				<div id="ledgix-scan-result" style="margin-top: 18px;"></div>

			</div>
		</div>
	`);

	function mount_quick_scan_navigator(retry = 0) {
		const $content = $(page.body).find(".lx-quick-scan-page").first();
		if (!$content.length || $content.closest(".ledgix-app-shell").length) return;
		if (!window.LedgixNavigator?.mount) {
			if (retry < 6) window.setTimeout(() => mount_quick_scan_navigator(retry + 1), 120);
			return;
		}
		window.LedgixNavigator.mount({
			page,
			wrapper,
			content: $content,
			activeKey: "operations",
		});
	}

	mount_quick_scan_navigator();

	function focus_input(force = false) {

		const input = $('#ledgix-scan-code');

		if (!input.length) {
			return;
		}

		setTimeout(() => {

			if (!force && $('.modal:visible').length) {
				return;
			}

			input.trigger('focus');

			const el = input.get(0);

			if (el) {
				el.focus();

				const value = el.value || '';
				el.setSelectionRange(value.length, value.length);
			}

		}, 120);
	}

	function set_status(type, message) {
		let bg = "#f3f4f6";
		let color = "#374151";

		if (type === "success") {
			bg = "#ecfdf5";
			color = "#065f46";
		}

		if (type === "danger") {
			bg = "#fff7ed";
			color = "#9a3412";
		}

		if (type === "loading") {
			bg = "#eff6ff";
			color = "#1d4ed8";
		}

		$('#ledgix-live-status').html(`
			<div style="
				padding: 10px 12px;
				border-radius: 12px;
				background: ${bg};
				color: ${color};
				font-weight: 600;
			">
				${message}
			</div>
		`);
	}

	function lookup_item_live() {
		const code = ($('#ledgix-scan-code').val() || '').trim();

		lastLookupCode = code;
		lastLookupResult = null;

		if (!code) {
			set_status("neutral", "Ready for scanner input.");
			focus_input();
			return;
		}

		set_status("loading", "Checking item...");

		frappe.call({
			method: 'ledgix_saas.api.api.get_item_by_barcode_or_sku',
			args: {
				code: code
			},
			callback: function(r) {
				const data = r.message;

				if (($('#ledgix-scan-code').val() || '').trim() !== code) {
					return;
				}

				lastLookupResult = data;

				if (data && data.found && data.item) {
					set_status(
						"success",
						`Item exists: ${data.item.item_name || data.item.name}`
					);

					focus_input();
					return;
				}

				set_status(
					"danger",
					"Item not found. Continue will start a new item entry."
				);

				focus_input();
			}
		});
	}

	function continue_item() {
		const code = ($('#ledgix-scan-code').val() || '').trim();

		if (!code) {
			frappe.msgprint('Please scan or enter barcode / SKU / item code');
			focus_input(true);
			return;
		}

		$('#ledgix-scan-result').html(`
			<div class="text-muted">Processing...</div>
		`);

		frappe.call({
			method: 'ledgix_saas.api.api.get_item_by_barcode_or_sku',
			args: {
				code: code
			},
			callback: function(r) {
				const data = r.message;

				if (data && data.found && data.item) {
					$('#ledgix-scan-result').html(`
						<div style="padding: 12px; border-radius: 12px; background: #ecfdf5; color: #065f46;">
							Item found. Opening existing item...
						</div>
					`);

					frappe.set_route('Form', 'Ledgix Item', data.item.name);
					return;
				}

				$('#ledgix-scan-result').html(`
					<div style="padding: 12px; border-radius: 12px; background: #fff7ed; color: #9a3412;">
						Item not found. Starting new item entry...
					</div>
				`);

				frappe.new_doc('Ledgix Item', {
					barcode: code
				});
			}
		});
	}

	function load_scanner_library(callback) {
		if (window.Html5Qrcode) {
			callback();
			return;
		}

		const script = document.createElement('script');
		script.src = 'https://unpkg.com/html5-qrcode';
		script.onload = callback;
		script.onerror = function() {
			frappe.msgprint('Unable to load camera scanner library');
		};

		document.head.appendChild(script);
	}

	function start_camera_scan() {
		load_scanner_library(function() {
			$('#ledgix-camera-area').show();

			if (!html5QrCode) {
				html5QrCode = new Html5Qrcode("ledgix-camera-reader");
			}

			if (cameraRunning) {
				return;
			}

			html5QrCode.start(
				{ facingMode: "environment" },
				{
					fps: 10,
					qrbox: {
						width: 320,
						height: 160
					}
				},
				function(decodedText) {
					$('#ledgix-scan-code').val(decodedText);
					lookup_item_live();

					stop_camera_scan(function() {
						continue_item();
					});
				}
			).then(function() {
				cameraRunning = true;
			}).catch(function(err) {
				frappe.msgprint('Camera scan could not start. Please allow camera permission.');
				console.error(err);
				focus_input(true);
			});
		});
	}

	function stop_camera_scan(callback) {
		if (!html5QrCode || !cameraRunning) {
			$('#ledgix-camera-area').hide();

			if (callback) {
				callback();
			}

			focus_input();
			return;
		}

		html5QrCode.stop().then(function() {
			cameraRunning = false;
			$('#ledgix-camera-area').hide();

			if (callback) {
				callback();
			}

			focus_input();
		}).catch(function(err) {
			console.error(err);

			if (callback) {
				callback();
			}

			focus_input();
		});
	}

	$('#ledgix-scan-code').on('input', function() {
		clearTimeout(lookupTimer);

		lookupTimer = setTimeout(function() {
			lookup_item_live();
		}, 350);
	});

	$('#ledgix-scan-code').on('keydown', function(e) {
		if (e.key === 'Enter') {
			e.preventDefault();
			continue_item();
		}
	});

	// ============================================================
	// KEEP SCANNER INPUT ALWAYS READY
	// ============================================================

	$('#ledgix-scan-code').on('blur', function() {

		setTimeout(() => {

			const activeElement = document.activeElement;

			const clickedButton =
				$(activeElement).closest('button').length;

			if (!clickedButton) {
				focus_input();
			}

		}, 150);
	});

	$(document).on('click', function(e) {

		const clickedInsideScanner =
			$(e.target).closest('#ledgix-scan-code').length;

		const clickedButton =
			$(e.target).closest('button').length;

		const clickedModal =
			$(e.target).closest('.modal').length;

		if (
			!clickedInsideScanner &&
			!clickedButton &&
			!clickedModal
		) {
			focus_input();
		}
	});

	$('#ledgix-continue-btn').on('click', continue_item);

	$('#ledgix-camera-btn').on('click', start_camera_scan);

	$('#ledgix-stop-camera-btn').on('click', function() {
		stop_camera_scan();
		focus_input(true);
	});

	$('#ledgix-clear-btn').on('click', function() {
		$('#ledgix-scan-code').val('');
		$('#ledgix-scan-result').html('');
		lastLookupCode = "";
		lastLookupResult = null;
		set_status("neutral", "Ready for scanner input.");
		stop_camera_scan();
		focus_input(true);
	});

	focus_input(true);
};
