import os
import time
from playwright.sync_api import sync_playwright

def run_automation():
    # Parámetros de configuración
    url = "http://localhost:8069/web?db=odoo_traductor_v2"
    username = "admin"
    password = "admin"
    pdf_filename = "nuevo123.pdf"
    
    # Obtener la ruta absoluta del PDF en el workspace
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(current_dir, pdf_filename)
    
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo PDF de prueba no existe en {pdf_path}")
        return

    print("Iniciando navegador Playwright en modo Headed (Visible)...")
    with sync_playwright() as p:
        # Lanzar Chromium con UI visible y slow_mo para simular interacción humana fluida
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        
        # Crear un contexto con el tamaño de ventana maximizado
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        
        # Paso 1: Navegar a la página de Odoo
        print(f"Navegando a {url}...")
        page.goto(url, timeout=90000)
        time.sleep(3)  # Pausa estratégica para la grabación
        
        # Paso 2: Iniciar sesión automáticamente
        print("Iniciando sesión...")
        if page.locator("input#login").is_visible():
            page.fill("input#login", username)
            time.sleep(1)
            page.fill("input#password", password)
            time.sleep(1)
            page.click("button[type='submit']")
            print("Sesión iniciada con éxito.")
        else:
            print("La pantalla de inicio de sesión no se detectó o ya se inició sesión.")
            
        time.sleep(4)  # Esperar a que cargue el dashboard
        
        # Paso 3: Navegar al menú "Traductor Inteligente"
        print("Navegando al módulo 'Traductor Inteligente'...")
        # Intentamos hacer clic en el icono de la aplicación en el dashboard
        app_icon = page.locator("a.o_app[data-menu-xmlid='translation_agent_intel.menu_translation_agent_root']")
        if app_icon.is_visible():
            app_icon.click()
        else:
            # Fallback: buscar por el texto del menú o navegar por URL directamente
            app_link = page.locator("text=Traductor Inteligente")
            if app_link.is_visible():
                app_link.click()
            else:
                print("Accediendo directamente mediante URL de la acción de Odoo...")
                page.goto("http://localhost:8069/web#action=translation_agent_intel.action_translation_job")
                
        time.sleep(3)  # Pausa de transición visual
        
        # Paso 4: Crear un nuevo trabajo de traducción
        print("Creando nuevo Trabajo de Traducción...")
        # En Odoo 16, el botón de creación en la vista de lista tiene la clase 'o_list_button_add' y dice 'Nuevo' o 'Crear'
        create_btn = page.locator("button.o_list_button_add, button:has-text('Nuevo'), button:has-text('Crear')").first
        create_btn.click()
        time.sleep(2)  # Pausa visual
        
        # Paso 5: Configurar los idiomas y el país de destino
        print("Configurando parámetros del trabajo...")
        
        # Odoo 16 Selection fields se renderizan como selects HTML o inputs de búsqueda.
        # Si son selectores estándar:
        source_select = page.locator("select[name='source_lang']")
        if source_select.is_visible():
            source_select.select_option("auto")  # Auto detectar
        time.sleep(1.5)
        
        target_select = page.locator("select[name='target_lang']")
        if target_select.is_visible():
            target_select.select_option("es_ES")  # Traducir a Español España
        time.sleep(1.5)
        
        country_select = page.locator("select[name='target_country']")
        if country_select.is_visible():
            country_select.select_option("ES")  # Enfoque comercial España
        time.sleep(1.5)
        
        # Paso 6: Subir el PDF
        print(f"Subiendo el archivo PDF de entrada: {pdf_filename}...")
        # Playwright maneja las subidas de archivos localizando el input[type=file] y asignando los archivos
        file_input = page.locator("input[type='file'][name='pdf_file'], input[type='file']").first
        file_input.set_input_files(pdf_path)
        time.sleep(3)  # Esperar a que Odoo cargue el archivo temporalmente en la UI
        
        # Paso 7: Iniciar Traducción Multi-Agente
        print("Iniciando pipeline de traducción multi-agente...")
        translate_btn = page.locator("button[name='action_start_translation'], button:has-text('Iniciar Traducción Multi-Agente')").first
        translate_btn.click()
        time.sleep(3)  # Pausa inicial tras hacer clic
        
        # Paso 8: Esperar a que finalice el procesamiento (concurrencia de fondo)
        print("Esperando la finalización de los agentes...")
        
        # Guardamos la URL actual para poder hacer reload
        current_url = page.url
        max_attempts = 20  # Ajustable según la velocidad de la API / PDF
        attempt = 0
        is_done = False
        
        while attempt < max_attempts and not is_done:
            attempt += 1
            print(f"Verificando estado (Intento {attempt}/{max_attempts})...")
            
            # Recargar la página para obtener el estado fresco de la BD
            page.goto(current_url)
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            
            # Buscar el elemento de estado activo en la barra de estado de Odoo (ej. 'Finalizado' o 'Borrador')
            # El estado en el statusbar puede ser leído desde la interfaz.
            # En Odoo 16, la barra de estado muestra los estados. El estado actual suele tener la clase o_arrow_button_current o similar.
            # Comprobamos si el estado es 'Finalizado' en la UI
            # También podemos verificar si el botón de descarga del Word (.docx) ya es visible.
            docx_link = page.locator("a:has-text('_final.docx'), .o_field_binary a").first
            
            # Comprobamos también visualmente el badge de estado si estuviera
            state_text = page.locator(".o_statusbar_status, .o_field_widget[name='state']").text_content()
            print(f"Estado en UI detectado: {state_text.strip() if state_text else 'No detectado'}")
            
            if docx_link.is_visible() or "Finalizado" in (state_text or ""):
                print("¡Traducción finalizada correctamente!")
                is_done = True
                break
            
            time.sleep(5)  # Esperar antes del siguiente refresco
            
        if not is_done:
            print("El proceso tomó más tiempo de lo esperado. Verifica el estado en la interfaz manualmente.")
            return

        # Paso 9: Descargar el archivo .docx generado
        print("Descargando el archivo traducido (.docx)...")
        # En Playwright, para descargar un archivo interceptamos el evento 'download'
        with page.expect_download() as download_info:
            docx_link.click()
            
        download = download_info.value
        output_path = os.path.join(current_dir, download.suggested_filename)
        download.save_as(output_path)
        print(f"Archivo descargado exitosamente en: {output_path}")
        time.sleep(4)  # Pausa final para que se grabe el resultado en el video
        
        # Cerrar navegador
        browser.close()
        print("Automatización completada con éxito.")

if __name__ == "__main__":
    run_automation()
