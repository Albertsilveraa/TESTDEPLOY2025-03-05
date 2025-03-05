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

# Configuración de la API de OpenAI:
# Puedes asignar tu API key directamente o asegurarte de tenerla en la variable de entorno OPENAI_API_KEY
#openai.api_key = os.getenv("OPENAI_API_KEY") or "TU_API_KEY_AQUI"
openai.api_key = ""


# Datos fijos del emisor (empresa)
EMPRESA = {
    "name": "GREENTER S.A.C.",
    "ruc": "20123456789",
    "direccion": "AV NEW DEÁL 123, CASUARINAS, LIMA"
}

# Ruta de la imagen del logo
LOGO_PATH = "logo.png"

# Función para obtener y actualizar el contador de boletas (almacenado en counter.txt)
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

# Función para generar el XML de la boleta
def generate_xml(emisor, cliente, products, invoice_number, totals):
    # Definir y registrar namespaces
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
    
    # Extensiones UBL
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
    cbc_InvoiceTypeCode.text = "03"  # 03 = Boleta de venta
    cbc_Note = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Note", {"languageLocaleID": "1000"})
    cbc_Note.text = f"SON {totals['total']:.2f} SOLES"
    cbc_DocumentCurrencyCode = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}DocumentCurrencyCode")
    cbc_DocumentCurrencyCode.text = "PEN"
    
    # Incluir la imagen del logo (codificada en base64)
    logo_element = ET.SubElement(root, "LogoImage")
    try:
        with open(LOGO_PATH, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        logo_element.text = encoded_string
    except Exception as e:
        logo_element.text = ""
    
    # Firma (simplificada)
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
    
    # Datos del emisor (AccountingSupplierParty)
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
    cbc_Line = ET.SubElement(ET.SubElement(cac_RegistrationAddress, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AddressLine"),
                               "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}Line")
    cbc_Line.text = emisor["direccion"]
    
    # Datos del cliente (AccountingCustomerParty)
    cac_AccountingCustomerParty = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}AccountingCustomerParty")
    cac_Party_cust = ET.SubElement(cac_AccountingCustomerParty, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Party")
    cac_PartyIdentification_cust = ET.SubElement(cac_Party_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyIdentification")
    cbc_ID_customer = ET.SubElement(cac_PartyIdentification_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID", {"schemeID": "1"})
    cbc_ID_customer.text = cliente["dni_ruc"]
    cac_PartyLegalEntity_cust = ET.SubElement(cac_Party_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}PartyLegalEntity")
    cbc_RegistrationName_cust = ET.SubElement(cac_PartyLegalEntity_cust, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}RegistrationName")
    cbc_RegistrationName_cust.text = cliente["nombre"]
    
    # Impuestos totales
    cac_TaxTotal = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}TaxTotal")
    cbc_TaxAmount = ET.SubElement(cac_TaxTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxAmount", {"currencyID": "PEN"})
    cbc_TaxAmount.text = f"{totals['igv']:.2f}"
    
    # Totales monetarios
    cac_LegalMonetaryTotal = ET.SubElement(root, "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}LegalMonetaryTotal")
    cbc_LineExtensionAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}LineExtensionAmount", {"currencyID": "PEN"})
    cbc_LineExtensionAmount.text = f"{totals['subtotal']:.2f}"
    cbc_TaxInclusiveAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}TaxInclusiveAmount", {"currencyID": "PEN"})
    cbc_TaxInclusiveAmount.text = f"{totals['total']:.2f}"
    cbc_PayableAmount = ET.SubElement(cac_LegalMonetaryTotal, "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}PayableAmount", {"currencyID": "PEN"})
    cbc_PayableAmount.text = f"{totals['total']:.2f}"
    
    # Detalle de cada producto (InvoiceLine)
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
    
    # Guardar el XML en archivo
    xml_file = f"boleta_{invoice_number}.xml"
    tree = ET.ElementTree(root)
    tree.write(xml_file, encoding="utf-8", xml_declaration=True)
    print(f"\nXML generado: {xml_file}")

# Función para generar el PDF de la boleta usando ReportLab
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
    p = Paragraph(f"<b>Boleta: {invoice_number}</b>", styles["Title"])
    flowables.append(p)
    flowables.append(Spacer(1, 12))
    
    # Datos del emisor y del cliente
    p_emisor = Paragraph(
        f"<b>Emisor:</b> {emisor['name']}<br/>RUC: {emisor['ruc']}<br/>Dirección: {emisor['direccion']}",
        styles["Normal"]
    )
    p_cliente = Paragraph(
        f"<b>Cliente:</b> {cliente['nombre']}<br/>DNI/RUC: {cliente['dni_ruc']}<br/>Dirección: {cliente['direccion']}",
        styles["Normal"]
    )
    flowables.append(p_emisor)
    flowables.append(Spacer(1, 12))
    flowables.append(p_cliente)
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
    
    # Construir el PDF
    doc.build(flowables)
    print(f"PDF generado: {pdf_file}")
    
    # Abrir automáticamente el PDF (funciona en Windows)
    try:
        os.startfile(pdf_file)
    except Exception as e:
        print("No se pudo abrir el PDF automáticamente.")

# MODO DE CONVERSACIÓN CON LA API DE OPENAI
def conversation_mode():
    print("\n--- MODO CONVERSACIONAL ---")
    print("Escribe 'salir' para volver al menú principal.\n")
    conversation_history = []
    while True:
        user_input = input("Tú: ").strip()
        if user_input.lower() == "salir":
            break
        # Agregar el mensaje del usuario al historial
        conversation_history.append({"role": "user", "content": user_input})
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=conversation_history,
                temperature=0.7,
                max_tokens=150
            )
            answer = response.choices[0].message['content'].strip()
            conversation_history.append({"role": "assistant", "content": answer})
            print("Agente:", answer)
        except Exception as e:
            print("Error al comunicarse con OpenAI:", str(e))
    print("--- Fin del modo conversacional ---\n")

# MODO DE GENERACIÓN DE BOLETAS
def invoice_mode():
    print("\n--- MODO GENERACIÓN DE BOLETAS ---")
    print("Escriba 'salir' en cualquier momento para volver al menú principal.\n")
    
    # Datos del cliente
    cliente_nombre = input("Ingrese el nombre del cliente: ").strip()
    if cliente_nombre.lower() == "salir":
        return
    cliente_dni = input("Ingrese el DNI/RUC del cliente: ").strip()
    if cliente_dni.lower() == "salir":
        return
    cliente_direccion = input("Ingrese la dirección del cliente: ").strip()
    if cliente_direccion.lower() == "salir":
        return
    cliente = {
        "nombre": cliente_nombre,
        "dni_ruc": cliente_dni,
        "direccion": cliente_direccion
    }
    
    # Ingreso de productos
    products = []
    print("\nIngrese los productos. Escriba 'fin' en el nombre del producto para terminar.")
    while True:
        prod_nombre = input("Nombre del producto: ").strip()
        if prod_nombre.lower() in ["fin", "salir"]:
            break
        try:
            prod_cantidad = float(input("Cantidad: ").strip())
            prod_precio = float(input("Precio unitario: ").strip())
        except ValueError:
            print("Cantidad y precio deben ser números. Intente nuevamente.")
            continue
        prod_subtotal = prod_cantidad * prod_precio
        prod_igv = prod_subtotal * 0.18  # IGV 18%
        products.append({
            "nombre": prod_nombre,
            "cantidad": prod_cantidad,
            "precio_unitario": prod_precio,
            "subtotal": prod_subtotal,
            "igv": prod_igv
        })
    
    if not products:
        print("No se ingresaron productos. Volviendo al menú principal...\n")
        return
    
    # Cálculo de totales
    total_subtotal = sum(p["subtotal"] for p in products)
    total_igv = sum(p["igv"] for p in products)
    total_total = total_subtotal + total_igv
    totals = {
        "subtotal": total_subtotal,
        "igv": total_igv,
        "total": total_total
    }
    
    # Obtener número de boleta (se incrementa automáticamente)
    invoice_number = get_next_invoice_number()
    
    # Mostrar resumen de la boleta
    print("\nResumen de la boleta:")
    print(f"Número de boleta: {invoice_number}")
    print(f"Cliente: {cliente['nombre']} - {cliente['dni_ruc']}")
    print(f"Dirección: {cliente['direccion']}")
    print("Productos:")
    for i, prod in enumerate(products, start=1):
        total_line = prod["subtotal"] + prod["igv"]
        print(f"  {i}. {prod['nombre']} - Cantidad: {prod['cantidad']}, Precio: {prod['precio_unitario']:.2f}, "
              f"Subtotal: {prod['subtotal']:.2f}, IGV: {prod['igv']:.2f}, Total: {total_line:.2f}")
    print(f"Subtotal: {totals['subtotal']:.2f}")
    print(f"IGV (18%): {totals['igv']:.2f}")
    print(f"Total a pagar: {totals['total']:.2f}\n")
    
    generar = input("¿Desea generar la boleta? (si/no): ").strip().lower()
    if generar == "si":
        generate_xml(EMPRESA, cliente, products, invoice_number, totals)
        generate_pdf(EMPRESA, cliente, products, invoice_number, totals)
    else:
        print("Boleta no generada.")
    print("--- Fin del modo generación de boletas ---\n")

# Función principal (menú del chatbot)
def main():
    print("Bienvenido al sistema de boletas electrónicas y agente conversacional.")
    while True:
        print("Opciones:")
        print("  1. Generar boleta")
        print("  2. Conversar con el agente")
        print("  salir - Para terminar el programa")
        opcion = input("Seleccione una opción: ").strip().lower()
        if opcion == "salir":
            break
        elif opcion in ["1", "generar boleta"]:
            invoice_mode()
        elif opcion in ["2", "conversar"]:
            conversation_mode()
        else:
            print("Opción no válida, intente nuevamente.\n")
    print("Programa finalizado.")

if __name__ == "__main__":
    main()
