import os
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Font initialization: Register TrueType Arial for native ₹ rendering if available
_FONT_INITIALIZED = False
_FONT_REGULAR = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'
_CURRENCY_SYMBOL = 'Rs. '

def _init_fonts():
    global _FONT_INITIALIZED, _FONT_REGULAR, _FONT_BOLD, _CURRENCY_SYMBOL
    if _FONT_INITIALIZED:
        return
    _FONT_INITIALIZED = True

    for font_path in ['C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/Arial.ttf']:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('ArialApp', font_path))
                _FONT_REGULAR = 'ArialApp'
                _CURRENCY_SYMBOL = '\u20b9'
                break
            except Exception:
                pass

    for font_path in ['C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/Arialbd.ttf']:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('ArialApp-Bold', font_path))
                _FONT_BOLD = 'ArialApp-Bold'
                break
            except Exception:
                pass

def format_inr(amount, symbol=None):
    """Formats amount using Indian numbering system (e.g. ₹1,26,000.00)."""
    if symbol is None:
        symbol = _CURRENCY_SYMBOL
    try:
        val = float(amount or 0)
        is_neg = val < 0
        val = abs(val)
        s = f"{val:.2f}"
        whole, dec = s.split('.')
        if len(whole) <= 3:
            res = whole
        else:
            last3 = whole[-3:]
            rest = whole[:-3]
            pairs = []
            while len(rest) > 2:
                pairs.append(rest[-2:])
                rest = rest[:-2]
            if rest:
                pairs.append(rest)
            pairs.reverse()
            res = ','.join(pairs) + ',' + last3
        prefix = '-' if is_neg else ''
        return f"{prefix}{symbol}{res}.{dec}"
    except Exception:
        return f"{symbol}{amount}"

def generate_invoice_pdf(invoice):
    """
    Generates a professional A4 company tax invoice PDF for FAB FORA INTERNATIONAL PVT. LTD.
    Reuses existing ReportLab and fits cleanly on a single A4 page.
    """
    _init_fonts()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32
    )

    story = []
    usable_width = doc.width

    # Typography Styles
    company_title_style = ParagraphStyle(
        'CompanyTitle',
        fontName=_FONT_BOLD,
        fontSize=14,
        leading=17,
        textColor=colors.HexColor('#0f172a')
    )
    company_tagline_style = ParagraphStyle(
        'CompanyTagline',
        fontName=_FONT_REGULAR,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0284c7')
    )
    company_sub_style = ParagraphStyle(
        'CompanySub',
        fontName=_FONT_REGULAR,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748b')
    )
    tax_invoice_title_style = ParagraphStyle(
        'TaxInvoiceTitle',
        fontName=_FONT_BOLD,
        fontSize=18,
        leading=22,
        alignment=2,
        textColor=colors.HexColor('#0284c7')
    )
    invoice_meta_style = ParagraphStyle(
        'InvoiceMeta',
        fontName=_FONT_REGULAR,
        fontSize=8.5,
        leading=12,
        alignment=2,
        textColor=colors.HexColor('#334155')
    )

    # Status color
    status_lower = (invoice.payment_status or 'Pending').lower()
    if 'paid' in status_lower and 'partial' not in status_lower:
        status_color = '#16a34a'
        status_label = 'PAID'
    elif 'partial' in status_lower:
        status_color = '#0284c7'
        status_label = 'PARTIALLY PAID'
    else:
        status_color = '#d97706'
        status_label = 'PENDING'

    status_badge_style = ParagraphStyle(
        'StatusBadge',
        fontName=_FONT_BOLD,
        fontSize=8.5,
        leading=11,
        alignment=2,
        textColor=colors.HexColor(status_color)
    )

    # 1. Header Table (Company Branding + TAX INVOICE)
    col_w = usable_width / 2.0
    header_left = [
        Paragraph('<b>FAB FORA INTERNATIONAL PVT. LTD.</b>', company_title_style),
        Paragraph('Garment Production &amp; Planning', company_tagline_style),
        Paragraph('Whitefield Export Apparel Park, Bangalore, KA, India', company_sub_style)
    ]
    header_right = [
        Paragraph('TAX INVOICE', tax_invoice_title_style),
        Paragraph(f'<b>Invoice No:</b> {invoice.invoice_number}', invoice_meta_style),
        Paragraph(f'<b>Invoice Date:</b> {invoice.invoice_date.strftime("%d-%m-%Y")}', invoice_meta_style),
        Paragraph(f'<b>Payment Status:</b> {status_label}', status_badge_style)
    ]

    header_table = Table([[header_left, header_right]], colWidths=[col_w, col_w])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=10, spaceBefore=0))

    # 2. Bill To & Order Details Cards
    card_title_style = ParagraphStyle('CardTitle', fontName=_FONT_BOLD, fontSize=8, leading=10, textColor=colors.HexColor('#64748b'))
    body_bold_style = ParagraphStyle('BodyBold', fontName=_FONT_BOLD, fontSize=9.5, leading=12, textColor=colors.HexColor('#0f172a'))
    body_text_style = ParagraphStyle('BodyText', fontName=_FONT_REGULAR, fontSize=8, leading=11, textColor=colors.HexColor('#334155'))

    cust = invoice.customer
    cust_user = getattr(cust, 'customer_user', None)

    bill_to_content = [
        Paragraph('<b>BILL TO</b>', card_title_style),
        Spacer(1, 3),
        Paragraph(cust.name if cust else 'Customer', body_bold_style),
        Paragraph(f'Customer ID: CUST-{(cust.id if cust else 0):04d}', body_text_style),
        Paragraph(f'Email: {cust.email if cust else "N/A"}', body_text_style),
        Paragraph(f'Phone: {cust.phone if cust else "N/A"}', body_text_style),
    ]
    if cust_user and cust_user.gst_number:
        bill_to_content.append(Paragraph(f'GSTIN: {cust_user.gst_number}', body_text_style))
    if cust_user and cust_user.billing_address:
        bill_to_content.append(Paragraph(f'Address: {cust_user.billing_address}', body_text_style))

    ord_obj = invoice.order
    order_info_content = [
        Paragraph('<b>ORDER DETAILS</b>', card_title_style),
        Spacer(1, 3),
        Paragraph(f'<b>Order Number:</b> #ORD-{(invoice.order_id):04d}', body_bold_style),
        Paragraph(f'<b>Garment Type:</b> {ord_obj.garment_type if ord_obj else "Garments"}', body_text_style),
        Paragraph(f'<b>Order Quantity:</b> {(ord_obj.quantity if ord_obj else 0):,} units', body_text_style),
        Paragraph(f'<b>Order Date:</b> {ord_obj.order_date.strftime("%d-%m-%Y") if ord_obj else "N/A"}', body_text_style),
        Paragraph(f'<b>Order Status:</b> {ord_obj.status if ord_obj else "Confirmed"}', body_text_style),
    ]

    card_w = (usable_width - 12) / 2.0
    info_table = Table([[bill_to_content, order_info_content]], colWidths=[card_w, card_w])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (0,0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (1,0), (1,0), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # 3. Itemized Billing Table
    th_style = ParagraphStyle('TH', fontName=_FONT_BOLD, fontSize=8.5, leading=10, textColor=colors.HexColor('#334155'))
    th_right_style = ParagraphStyle('THRight', fontName=_FONT_BOLD, fontSize=8.5, leading=10, alignment=2, textColor=colors.HexColor('#334155'))
    td_style = ParagraphStyle('TD', fontName=_FONT_REGULAR, fontSize=8.5, leading=11, textColor=colors.HexColor('#0f172a'))
    td_desc_sub = ParagraphStyle('TDSub', fontName=_FONT_REGULAR, fontSize=7.5, leading=9, textColor=colors.HexColor('#64748b'))
    td_right_style = ParagraphStyle('TDRight', fontName=_FONT_REGULAR, fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#0f172a'))

    garment_name = ord_obj.garment_type if ord_obj else "Garment Batch"
    qty_val = ord_obj.quantity if ord_obj else 1
    rate_val = invoice.derived_rate

    item_desc = [
        Paragraph(f'<b>{garment_name}</b>', td_style),
        Paragraph('Industrial batch manufacturing &amp; apparel finishing', td_desc_sub)
    ]

    items_data = [
        [
            Paragraph('DESCRIPTION', th_style),
            Paragraph('QUANTITY', th_right_style),
            Paragraph('RATE', th_right_style),
            Paragraph('AMOUNT', th_right_style)
        ],
        [
            item_desc,
            Paragraph(f'{qty_val:,}', td_right_style),
            Paragraph(format_inr(rate_val), td_right_style),
            Paragraph(format_inr(invoice.subtotal), td_right_style)
        ]
    ]

    # Column widths summing to usable_width
    col0 = 230
    col1 = 70
    col2 = 100
    col3 = usable_width - (col0 + col1 + col2)

    items_table = Table(items_data, colWidths=[col0, col1, col2, col3])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#cbd5e1')),
        ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # 4. Totals Breakdown & Notes
    totals_label_style = ParagraphStyle('TotLabel', fontName=_FONT_REGULAR, fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#475569'))
    totals_val_style = ParagraphStyle('TotVal', fontName=_FONT_REGULAR, fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#0f172a'))
    gt_label_style = ParagraphStyle('GTLabel', fontName=_FONT_BOLD, fontSize=11, leading=13, alignment=2, textColor=colors.HexColor('#0284c7'))
    gt_val_style = ParagraphStyle('GTVal', fontName=_FONT_BOLD, fontSize=11, leading=13, alignment=2, textColor=colors.HexColor('#0284c7'))

    notes_col = [
        Paragraph('<b>Payment Status &amp; Verification</b>', ParagraphStyle('N1', fontName=_FONT_BOLD, fontSize=8.5, leading=11, textColor=colors.HexColor('#0f172a'))),
        Spacer(1, 3),
        Paragraph(f'Payment Status: <font color="{status_color}"><b>{status_label}</b></font>', ParagraphStyle('N2', fontName=_FONT_REGULAR, fontSize=8, leading=10, textColor=colors.HexColor('#334155'))),
        Spacer(1, 6),
        Paragraph('<i>Thank you for your business.</i>', ParagraphStyle('N3', fontName=_FONT_REGULAR, fontSize=8, leading=10, textColor=colors.HexColor('#64748b'))),
        Spacer(1, 4),
        Paragraph('This is an authentic computer-generated commercial tax invoice issued by FAB FORA INTERNATIONAL PVT. LTD.', ParagraphStyle('N4', fontName=_FONT_REGULAR, fontSize=7, leading=9, textColor=colors.HexColor('#94a3b8'))),
    ]

    taxable = invoice.subtotal + invoice.additional_charges - invoice.discount
    totals_rows = [
        [Paragraph('Subtotal:', totals_label_style), Paragraph(format_inr(invoice.subtotal), totals_val_style)],
    ]
    if invoice.additional_charges and invoice.additional_charges > 0:
        totals_rows.append([Paragraph('Additional Charges:', totals_label_style), Paragraph(format_inr(invoice.additional_charges), totals_val_style)])
    if invoice.discount and invoice.discount > 0:
        totals_rows.append([Paragraph('Discount:', totals_label_style), Paragraph(f"-{format_inr(invoice.discount)}", totals_val_style)])
    
    totals_rows.append([Paragraph('Taxable Amount:', totals_label_style), Paragraph(format_inr(taxable), totals_val_style)])
    totals_rows.append([Paragraph(f'Tax ({invoice.tax_percentage}%):', totals_label_style), Paragraph(format_inr(invoice.tax_amount), totals_val_style)])
    totals_rows.append([Paragraph('GRAND TOTAL:', gt_label_style), Paragraph(format_inr(invoice.total_amount), gt_val_style)])

    tot_w = 240
    t_summary = Table(totals_rows, colWidths=[tot_w - 110, 110])
    t_summary.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-2), 3),
        ('BOTTOMPADDING', (0,0), (-1,-2), 3),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor('#0284c7')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f0f9ff')),
        ('TOPPADDING', (0,-1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,-1), (-1,-1), 6),
    ]))

    notes_w = usable_width - tot_w
    bottom_section = Table([[notes_col, t_summary]], colWidths=[notes_w, tot_w])
    bottom_section.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(bottom_section)
    story.append(Spacer(1, 20))

    # 5. Signature Block
    sig_text_style = ParagraphStyle('Sig', fontName=_FONT_REGULAR, fontSize=8, leading=10, alignment=2, textColor=colors.HexColor('#475569'))
    sig_title_style = ParagraphStyle('SigT', fontName=_FONT_BOLD, fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#0f172a'))

    sig_w = 230
    left_sig_w = usable_width - sig_w
    sig_table = Table([[
        Paragraph('', sig_text_style),
        [
            Paragraph('__________________________________________', sig_text_style),
            Spacer(1, 2),
            Paragraph('<b>Authorized Signature</b>', sig_title_style),
            Paragraph('FAB FORA INTERNATIONAL PVT. LTD.', sig_text_style)
        ]
    ]], colWidths=[left_sig_w, sig_w])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
