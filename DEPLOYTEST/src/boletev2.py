import os
import datetime
import base64
import xml.etree.ElementTree as ET
import openai

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# -------------------------
# CONFIGURACIÓN DE CLAVES
# -------------------------
# Reemplaza con tu token de Telegram
TELEGRAM_BOT_TOKEN = ""

# Configura tu API key de OpenAI (puedes usar variable de entorno o asignarla directamente)
#openai.api_key = os.getenv("OPENAI_API_KEY") or "TU_OPENAI_API_KEY_AQUI"
openai.api_key= ""
# -------------------------
# DATOS DEL EMISOR Y ARCHIVOS
# -------------------------
EMPRESA = {
    "name": "GREENTER S.A.C.",
    "ruc": "20123456789",
    "direccion": "AV NEW DEÁL 123, CASUARINAS, LIMA"
}
LOGO_PATH = "logo.png"

# -------------------------
# FUNCIÓN: Contador de boletas
# -------------------------
def get_next_invoice_number():
    counter_file = "counter.txt"
    try:
        with open(counter_file, "r") as f:
            count = int(f.read().strip())
    except FileNotFoundError:
        count = 1
    next_count = count + 1
    with open(counter_file, "w") as f:
        f.write(str(next_count))
    return f"B001-{count:06d}"  # Ejemplo: B001-000001

# -------------------------
# FUNCIÓN: Generación de XML
# -------------------------
def generate_xml(emisor, cliente, products, invoice_number, totals):
    ns = {
        "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    }
    for prefix, uri in ns.items():
        ET.register_namespace(prefix, uri)
    
    root = ET.Element("Invoice")
    
    # UBL Extensions
    ext_UBLExtensions = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}UBLExtensions")
    ext_UBLExtension = ET.SubElement(ext_UBLExtensions, "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}UBLExtension")
    ET.SubElement(ext_UBLExtension, "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}ExtensionContent")
    
    # Versión y personalización
    cbc_UBLVersionID = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}UBLVersionID")
    cbc_UBLVersionID.text = "2.1"
    cbc_CustomizationID = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}CustomizationID")
    cbc_CustomizationID.text = "2.0"
    
    # Número de boleta
    cbc_ID = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
    cbc_ID.text = invoice_number
    
    # Fecha y hora de emisión
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().time().isoformat(timespec="seconds")
    cbc_IssueDate = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueDate")
    cbc_IssueDate.text = today
    cbc_IssueTime = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}IssueTime")
    cbc_IssueTime.text = now
    
    # Tipo de documento y nota
    cbc_InvoiceTypeCode = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoiceTypeCode")
    cbc_InvoiceTypeCode.text = "03"  # Boleta de venta
    cbc_Note = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Note", {"languageLocaleID": "1000"})
    cbc_Note.text = f"SON {totals['total']:.2f} SOLES"
    cbc_DocumentCurrencyCode = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}DocumentCurrencyCode")
    cbc_DocumentCurrencyCode.text = "PEN"
    
    # Incluir logo codificado en base64
    logo_element = ET.SubElement(root, "LogoImage")
    try:
        with open(LOGO_PATH, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        logo_element.text = encoded_string
    except Exception as e:
        logo_element.text = ""
    
    # Firma simplificada
    cac_Signature = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Signature")
    cbc_ID_sig = ET.SubElement(cac_Signature, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
    cbc_ID_sig.text = emisor["ruc"]
    cac_SignatoryParty = ET.SubElement(cac_Signature, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}SignatoryParty")
    cac_PartyIdentification = ET.SubElement(cac_SignatoryParty, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification")
    cbc_ID_party = ET.SubElement(cac_PartyIdentification, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
    cbc_ID_party.text = emisor["ruc"]
    cac_PartyName = ET.SubElement(cac_SignatoryParty, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName")
    cbc_Name = ET.SubElement(cac_PartyName, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name")
    cbc_Name.text = emisor["name"]
    
    # Datos del emisor
    cac_AccountingSupplierParty = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingSupplierParty")
    cac_Party = ET.SubElement(cac_AccountingSupplierParty, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")
    cac_PartyIdentification = ET.SubElement(cac_Party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification")
    cbc_ID_supplier = ET.SubElement(cac_PartyIdentification, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID", {"schemeID": "6"})
    cbc_ID_supplier.text = emisor["ruc"]
    cac_PartyName = ET.SubElement(cac_Party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyName")
    cbc_Name_supplier = ET.SubElement(cac_PartyName, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Name")
    cbc_Name_supplier.text = emisor["name"]
    cac_PartyLegalEntity = ET.SubElement(cac_Party, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyLegalEntity")
    cbc_RegistrationName = ET.SubElement(cac_PartyLegalEntity, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}RegistrationName")
    cbc_RegistrationName.text = emisor["name"]
    cac_RegistrationAddress = ET.SubElement(cac_PartyLegalEntity, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}RegistrationAddress")
    cbc_Line = ET.SubElement(
        ET.SubElement(cac_RegistrationAddress, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AddressLine"),
        "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Line"
    )
    cbc_Line.text = emisor["direccion"]
    
    # Datos del cliente
    cac_AccountingCustomerParty = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingCustomerParty")
    cac_Party_cust = ET.SubElement(cac_AccountingCustomerParty, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")
    cac_PartyIdentification_cust = ET.SubElement(cac_Party_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification")
    cbc_ID_customer = ET.SubElement(cac_PartyIdentification_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID", {"schemeID": "1"})
    cbc_ID_customer.text = cliente["dni_ruc"]
    cac_PartyLegalEntity_cust = ET.SubElement(cac_Party_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyLegalEntity")
    cbc_RegistrationName_cust = ET.SubElement(cac_PartyLegalEntity_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}RegistrationName")
    cbc_RegistrationName_cust.text = cliente["nombre"]
    
    # Totales e impuestos
    cac_TaxTotal = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal")
    cbc_TaxAmount = ET.SubElement(cac_TaxTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount", {"currencyID": "PEN"})
    cbc_TaxAmount.text = f"{totals['igv']:.2f}"
    
    cac_LegalMonetaryTotal = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}LegalMonetaryTotal")
    cbc_LineExtensionAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount", {"currencyID": "PEN"})
    cbc_LineExtensionAmount.text = f"{totals['subtotal']:.2f}"
    cbc_TaxInclusiveAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxInclusiveAmount", {"currencyID": "PEN"})
    cbc_TaxInclusiveAmount.text = f"{totals['total']:.2f}"
    cbc_PayableAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PayableAmount", {"currencyID": "PEN"})
    cbc_PayableAmount.text = f"{totals['total']:.2f}"
    
    # Detalle de productos
    for i, prod in enumerate(products, start=1):
        cac_InvoiceLine = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine")
        cbc_ID_line = ET.SubElement(cac_InvoiceLine, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID")
        cbc_ID_line.text = str(i)
        cbc_InvoicedQuantity = ET.SubElement(cac_InvoiceLine, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}InvoicedQuantity", {"unitCode": "NIU"})
        cbc_InvoicedQuantity.text = str(prod["cantidad"])
        cbc_LineExtensionAmount = ET.SubElement(cac_InvoiceLine, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount", {"currencyID": "PEN"})
        cbc_LineExtensionAmount.text = f"{prod['subtotal']:.2f}"
        
        # Datos del producto
        cac_Item = ET.SubElement(cac_InvoiceLine, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Item")
        cbc_Description = ET.SubElement(cac_Item, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Description")
        cbc_Description.text = prod["nombre"]
        cac_Price = ET.SubElement(cac_InvoiceLine, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Price")
        cbc_PriceAmount = ET.SubElement(cac_Price, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PriceAmount", {"currencyID": "PEN"})
        cbc_PriceAmount.text = f"{prod['precio_unitario']:.2f}"
    
    xml_file = f"boleta_{invoice_number}.xml"
    tree = ET.ElementTree(root)
    tree.write(xml_file, encoding="utf-8", xml_declaration=True)
    print(f"XML generado: {xml_file}")

# -------------------------
# FUNCIÓN: Generación de PDF
# -------------------------
def generate_pdf(emisor, cliente, products, invoice_number, totals):
    pdf_file = f"boleta_{invoice_number}.pdf"
    doc = SimpleDocTemplate(pdf_file, pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []

    # Encabezado con logo (si existe)
    if os.path.exists(LOGO_PATH):
        im = Image(LOGO_PATH)
        im.drawHeight = 1 * inch
        im.drawWidth = 1 * inch
        flowables.append(im)
    flowables.append(Spacer(1, 12))
    
    # Número de boleta
    flowables.append(Paragraph(f"<b>Boleta: {invoice_number}</b>", styles["Title"]))
    flowables.append(Spacer(1, 12))
    
    # Datos del emisor y cliente
    flowables.append(Paragraph(
        f"<b>Emisor:</b> {emisor['name']}<br/>RUC: {emisor['ruc']}<br/>Dirección: {emisor['direccion']}",
        styles["Normal"]
    ))
    flowables.append(Spacer(1, 12))
    flowables.append(Paragraph(
        f"<b>Cliente:</b> {cliente['nombre']}<br/>DNI/RUC: {cliente['dni_ruc']}<br/>Dirección: {cliente['direccion']}",
        styles["Normal"]
    ))
    flowables.append(Spacer(1, 12))
    
    # Tabla de productos
    data = [["N°", "Producto", "Cantidad", "Precio Unitario", "Subtotal", "IGV", "Total"]]
    for i, prod in enumerate(products, start=1):
        total_line = prod["subtotal"] + prod["igv"]
        data.append([
            str(i),
            prod["nombre"],
            str(prod["cantidad"]),
            f"{prod['precio_unitario']:.2f}",
            f"{prod['subtotal']:.2f}",
            f"{prod['igv']:.2f}",
            f"{total_line:.2f}"
        ])
    table = Table(data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    flowables.append(table)
    flowables.append(Spacer(1, 12))
    
    # Totales
    data_totals = [
        ["Subtotal", f"{totals['subtotal']:.2f}"],
        ["IGV (18%)", f"{totals['igv']:.2f}"],
        ["Total", f"{totals['total']:.2f}"]
    ]
    table_totals = Table(data_totals, colWidths=[100, 100], hAlign='RIGHT')
    table_totals.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)
    ]))
    flowables.append(table_totals)
    
    doc.build(flowables)
    print(f"PDF generado: {pdf_file}")
    return pdf_file

# -------------------------
# FUNCIÓN: Agente conversacional con OpenAI  
# -------------------------
def ai_generate_message(step, data):
    system_prompt = (
        "Eres un asistente experto en generación de boletas electrónicas en Perú. "
        "Tu tarea es guiar al usuario de forma amigable y profesional para recopilar "
        "la información necesaria y generar una boleta electrónica."
    )
    if step == "ask_client_name":
        user_prompt = "El usuario iniciará la creación de una boleta electrónica. Pide al usuario que ingrese el nombre completo del cliente."
    elif step == "ask_client_dni":
        user_prompt = f"El cliente se llama {data.get('client_name', '')}. Ahora pide al usuario que ingrese el DNI o RUC del cliente."
    elif step == "ask_client_address":
        user_prompt = "Ahora pide al usuario que ingrese la dirección del cliente."
    elif step == "ask_product":
        user_prompt = "Pide al usuario que ingrese un producto en el siguiente formato: nombre, cantidad, precio unitario. Si ha terminado, que escriba 'fin'."
    elif step == "ask_confirmation":
        client_name = data.get("client_name", "")
        client_dni = data.get("client_dni", "")
        client_address = data.get("client_address", "")
        products = data.get("products", [])
        summary = f"Nombre: {client_name}\nDNI/RUC: {client_dni}\nDirección: {client_address}\nProductos:\n"
        for i, prod in enumerate(products, start=1):
            summary += f"{i}. {prod['nombre']} - Cantidad: {prod['cantidad']}, Precio: {prod['precio_unitario']}\n"
        user_prompt = f"El resumen de la boleta es:\n{summary}\n¿Desea generar la boleta? Responda 'sí' para confirmar o 'no' para cancelar."
    else:
        user_prompt = ""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        defaults = {
            "ask_client_name": "Por favor, ingrese el nombre completo del cliente.",
            "ask_client_dni": "Por favor, ingrese el DNI o RUC del cliente.",
            "ask_client_address": "Por favor, ingrese la dirección del cliente.",
            "ask_product": "Ingrese un producto en el formato: nombre, cantidad, precio unitario. Escriba 'fin' para terminar.",
            "ask_confirmation": "¿Desea generar la boleta? Responda 'sí' para confirmar o 'no' para cancelar."
        }
        return defaults.get(step, "")

# -------------------------
# Estados de la conversación
# -------------------------
GET_CLIENT_NAME, GET_CLIENT_DNI, GET_CLIENT_ADDRESS, GET_PRODUCT, CONFIRMATION = range(5)

# -------------------------
# Handlers para el ConversationHandler de Telegram
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenido al asistente de generación de boletas electrónicas.\n"
        "Para iniciar la creación de una boleta, usa el comando /crear_boleta."
    )

async def crear_boleta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['products'] = []
    message = ai_generate_message("ask_client_name", context.user_data)
    await update.message.reply_text(message)
    return GET_CLIENT_NAME

async def client_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_name = update.message.text.strip()
    context.user_data['client_name'] = client_name
    message = ai_generate_message("ask_client_dni", context.user_data)
    await update.message.reply_text(message)
    return GET_CLIENT_DNI

async def client_dni_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_dni = update.message.text.strip()
    context.user_data['client_dni'] = client_dni
    message = ai_generate_message("ask_client_address", context.user_data)
    await update.message.reply_text(message)
    return GET_CLIENT_ADDRESS

async def client_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_address = update.message.text.strip()
    context.user_data['client_address'] = client_address
    message = ai_generate_message("ask_product", context.user_data)
    await update.message.reply_text(message)
    return GET_PRODUCT

async def product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "fin":
        message = ai_generate_message("ask_confirmation", context.user_data)
        await update.message.reply_text(message)
        return CONFIRMATION
    else:
        parts = text.split(',')
        if len(parts) != 3:
            await update.message.reply_text("Formato incorrecto. Por favor, ingrese el producto en el formato: nombre, cantidad, precio unitario.")
            return GET_PRODUCT
        try:
            nombre = parts[0].strip()
            cantidad = float(parts[1].strip())
            precio = float(parts[2].strip())
        except ValueError:
            await update.message.reply_text("Cantidad y precio deben ser números. Inténtalo de nuevo.")
            return GET_PRODUCT
        product = {
            "nombre": nombre,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "subtotal": cantidad * precio,
            "igv": cantidad * precio * 0.18
        }
        context.user_data['products'].append(product)
        message = ai_generate_message("ask_product", context.user_data)
        await update.message.reply_text("Producto agregado.\n" + message)
        return GET_PRODUCT

async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text in ["sí", "si"]:
        invoice_number = get_next_invoice_number()
        products = context.user_data.get('products', [])
        total_subtotal = sum(p["subtotal"] for p in products)
        total_igv = sum(p["igv"] for p in products)
        total_total = total_subtotal + total_igv
        totals = {"subtotal": total_subtotal, "igv": total_igv, "total": total_total}
        client = {
            "nombre": context.user_data.get("client_name", ""),
            "dni_ruc": context.user_data.get("client_dni", ""),
            "direccion": context.user_data.get("client_address", "")
        }
        generate_xml(EMPRESA, client, products, invoice_number, totals)
        pdf_file = generate_pdf(EMPRESA, client, products, invoice_number, totals)
        await update.message.reply_text(f"Boleta generada con número {invoice_number}. Enviando PDF...")
        with open(pdf_file, 'rb') as f:
            await update.message.reply_document(document=InputFile(f, filename=pdf_file))
        return ConversationHandler.END
    else:
        await update.message.reply_text("Proceso cancelado. Usa /crear_boleta para iniciar de nuevo.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

# -------------------------
# Función principal: Inicia el bot de Telegram
# -------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('crear_boleta', crear_boleta)],
        states={
            GET_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_name_handler)],
            GET_CLIENT_DNI: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_dni_handler)],
            GET_CLIENT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_address_handler)],
            GET_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_handler)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
