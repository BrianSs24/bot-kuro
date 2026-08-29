import discord
from discord.ext import commands, tasks
import psycopg2
import re
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Canales
CANAL_KURO_ID = 1331359760414539791
CANAL_TNA_ID = 1339641817980866700
CANAL_CMD_ID = 1278916162117177385

# =========================
# NOMBRE EXACTO BOT MINELATINO
# =========================

BOTS_PERMITIDOS = [
    "MineLatino",
    "Ultimate Clans V7"
]

# =========================
# ROLES PRINCIPALES
# =========================

ALLOWED_ROLES = [
    935248281980796948,
    920144442843885639,
    1157136068613767268
]

# =========================
# TOTALES GENERALES CLANES
# =========================

TOTAL_CLAN_KURO = 0
TOTAL_CLAN_TNA = 0

# =========================
# CONFIGURACIÓN SEMANAL
# =========================

TZ = ZoneInfo("America/Santo_Domingo")
# Domingo a las 23:59:59, hora de República Dominicana.
DIA_FIN_SEMANA = 6
HORA_FIN_SEMANA = 23
MINUTO_FIN_SEMANA = 59

# True = sistema semanal activo. False = no acumula ni cierra semanas.
SEMANA_ACTIVA = True

# Tablas que se publican al finalizar la semana:
# "kuro" = solo Kuro
# "tna" = solo TNA
# "ambas" = Kuro y TNA
TABLAS_AL_FINALIZAR = "tna"

# =========================
# FUNCIONES
# =========================

def tiene_permiso(ctx):
    return any(role.id in ALLOWED_ROLES for role in ctx.author.roles)

def puede_usar_comando(ctx):

    # Roles permitidos = cualquier canal
    if tiene_permiso(ctx):
        return True

    # Usuarios normales = solo canal cmd
    return ctx.channel.id == CANAL_CMD_ID

# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DB FUNCTION
# =========================

def ejecutar(query, params=None, fetch=False):

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    cur.execute(query, params)

    data = None

    if fetch:
        data = cur.fetchall()

    conn.commit()

    cur.close()
    conn.close()

    return data

# =========================
# CREAR TABLAS
# =========================

ejecutar("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

ejecutar("""
CREATE TABLE IF NOT EXISTS puntos_tna (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")
ejecutar("""
CREATE TABLE IF NOT EXISTS puntos_kuro_semanal (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

ejecutar("""
CREATE TABLE IF NOT EXISTS puntos_tna_semanal (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

ejecutar("""
CREATE TABLE IF NOT EXISTS estado_semanal (
    id INTEGER PRIMARY KEY,
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ NOT NULL
)
""")

# =========================
# SISTEMA SEMANAL
# =========================

def calcular_fin_semana():
    ahora = datetime.now(TZ)
    dias = (DIA_FIN_SEMANA - ahora.weekday()) % 7
    fin = (ahora + timedelta(days=dias)).replace(
        hour=HORA_FIN_SEMANA,
        minute=MINUTO_FIN_SEMANA,
        second=59,
        microsecond=999999
    )
    if fin <= ahora:
        fin += timedelta(days=7)
    return fin


def inicializar_periodo_semanal():
    data = ejecutar(
        "SELECT inicio, fin FROM estado_semanal WHERE id = 1",
        fetch=True
    )

    if not data:
        fin = calcular_fin_semana()
        inicio = fin - timedelta(days=7) + timedelta(microseconds=1)
        ejecutar("""
            INSERT INTO estado_semanal (id, inicio, fin)
            VALUES (1, %s, %s)
        """, (inicio, fin))
        return inicio, fin

    inicio, fin = data[0]
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=TZ)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=TZ)
    return inicio.astimezone(TZ), fin.astimezone(TZ)


async def comprobar_cierre_semanal():
    if not SEMANA_ACTIVA:
        return

    ahora = datetime.now(TZ)
    inicio, fin = inicializar_periodo_semanal()

    if ahora < fin:
        return

    # Obtener los TOP antes de borrar los datos.
    kuro = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    tna = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_tna_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    def construir_top(titulo, data):
        if not data:
            return f"🏆 **{titulo}**\\n\\nNo hubo puntos registrados esta semana.\\n"

        texto = f"🏆 **{titulo}**\\n\\n"
        for i, (usuario, puntos) in enumerate(data, 1):
            texto += f"{i}. {usuario} → {puntos:,}\\n"
        return texto

    seleccion = TABLAS_AL_FINALIZAR.lower().strip()

    if seleccion == "kuro":
        bloques = [construir_top("KURO — TOP SEMANAL", kuro)]
    elif seleccion == "tna":
        bloques = [construir_top("TNA — TOP SEMANAL", tna)]
    elif seleccion == "ambas":
        bloques = [
            construir_top("KURO — TOP SEMANAL", kuro),
            construir_top("TNA — TOP SEMANAL", tna)
        ]
    else:
        print(f"⚠️ TABLAS_AL_FINALIZAR='{TABLAS_AL_FINALIZAR}' no es válida. Se usará TNA.")
        bloques = [construir_top("TNA — TOP SEMANAL", tna)]

    mensaje_inicial = (
        "🏁 **TABLA DE PUNTOS SEMANAL FINALIZADA** 🏁\\n\\n"
        "La acumulación de puntos de esta semana ha terminado."
    )

    mensaje_final = "♻️ Las puntuaciones semanales serán reiniciadas ahora."

    # Enviar el resultado final antes de borrar los datos.
    for canal_id in (CANAL_KURO_ID, CANAL_TNA_ID):
        canal = bot.get_channel(canal_id)
        if canal:
            try:
                partes = [mensaje_inicial] + bloques + [mensaje_final]

                for parte in partes:
                    if len(parte) <= 1900:
                        await canal.send(parte)
                    else:
                        actual = ""
                        for linea in parte.splitlines():
                            if len(actual) + len(linea) + 1 > 1900:
                                await canal.send(actual)
                                actual = ""
                            actual += linea + "\\n"
                        if actual:
                            await canal.send(actual)

            except Exception as e:
                print("❌ ERROR ENVIANDO TOP SEMANAL FINAL:", e)

    # Ahora sí se reinician únicamente las tablas semanales.
    ejecutar("DELETE FROM puntos_kuro_semanal")
    ejecutar("DELETE FROM puntos_tna_semanal")

    nuevo_inicio = fin + timedelta(microseconds=1)
    nuevo_fin = nuevo_inicio + timedelta(days=7) - timedelta(microseconds=1)

    ejecutar("""
        UPDATE estado_semanal
        SET inicio = %s, fin = %s
        WHERE id = 1
    """, (nuevo_inicio, nuevo_fin))

    print("♻️ SEMANA CERRADA: TOP PUBLICADO Y PUNTOS SEMANALES REINICIADOS")


@tasks.loop(minutes=1)
async def revisar_semana():
    try:
        await comprobar_cierre_semanal()
    except Exception as e:
        print("❌ ERROR REVISANDO SEMANA:", e)


@revisar_semana.before_loop
async def antes_de_revisar_semana():
    await bot.wait_until_ready()
    inicializar_periodo_semanal()

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

    if not revisar_semana.is_running():
        revisar_semana.start()

# =========================
# EXTRAER DATOS
# =========================

def extraer_datos(texto):

    # Formato nuevo:
    # (usuario +10.000 XP | Total: 50000)
    # (usuario +10.000 XP | Total: INVALID_TYPE)
    match_nuevo = re.search(
        r"\(([A-Za-z0-9_.]+)\s*\+([\d.,]+)\s*XP\b",
        texto,
        re.IGNORECASE
    )

    match_nuevo = re.search(
    r"\(\.?([A-Za-z0-9_]+)\s+\+([\d\.,]+)\s+XP",
    texto,
    re.IGNORECASE
)

if match_nuevo:

    usuario = match_nuevo.group(1).lower()

    puntos = int(
        match_nuevo.group(2)
        .replace(".", "")
        .replace(",", "")
    )

    return usuario, puntos
    # Formato antiguo:
    # usuario ha conseguido 10.000 puntos
    match_antiguo = re.search(
        r"([\w\d_.]+)\s+ha\s+conseguido\s+([\d.,]+)",
        texto,
        re.IGNORECASE
    )

    if match_antiguo:

        usuario = match_antiguo.group(1).lower()

        puntos = int(
            match_antiguo.group(2)
            .replace(".", "")
            .replace(",", "")
        )

        return usuario, puntos

    return None, None

@bot.event
async def on_message(message):

    global TOTAL_CLAN_KURO
    global TOTAL_CLAN_TNA
        
    # Procesar comandos siempre
    await bot.process_commands(message)

    # Ignorar usuarios normales
    if not message.author.bot:
        return

    # Detectar bots permitidos
    bot_valido = False

    for nombre in BOTS_PERMITIDOS:

        if nombre.lower() in message.author.name.lower():
            bot_valido = True
            break

    if not bot_valido:
        return

    # =========================
    # LEER CONTENIDO
    # =========================

    contenido = message.content or ""

    for embed in message.embeds:

        if embed.title:
            contenido += " " + embed.title

        if embed.description:
            contenido += " " + embed.description

        for field in embed.fields:
            contenido += f" {field.name} {field.value}"

    print("\n====================")
    print("📩 MENSAJE MINELATINO DETECTADO")
    print("BOT:", message.author.name)
    print("ID:", message.author.id)
    print("CANAL:", message.channel.id)
    print("CONTENIDO:", contenido)

    usuario, puntos = extraer_datos(contenido)

    if not usuario:
        print("❌ NO SE PUDO EXTRAER USUARIO/PUNTOS")
        return

    try:

        # =========================
        # KURO
        # =========================

        if message.channel.id == CANAL_KURO_ID:

            total_match = re.search(
                r"ahora tiene\s+([\d\.,]+)",
                contenido,
                re.IGNORECASE
            )

            if total_match:

                TOTAL_CLAN_KURO = int(
                    total_match.group(1)
                    .replace(".", "")
                    .replace(",", "")
                )
                total_match = re.search(
                r"ahora tiene\s+([\d\.,]+)\s+puntos",
                contenido,
                re.IGNORECASE
                )
            ejecutar("""
                INSERT INTO puntos_kuro (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            if SEMANA_ACTIVA:
                ejecutar("""
                    INSERT INTO puntos_kuro_semanal (usuario, puntos)
                    VALUES (%s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET puntos = puntos_kuro_semanal.puntos + EXCLUDED.puntos
                """, (usuario, puntos))

            print("💾 KURO GUARDADO (GENERAL + SEMANAL)")

            await message.channel.send(
                f"✅ {usuario} +{puntos:,} puntos KURO"
            )

        # =========================
        # TNA
        # =========================

        elif message.channel.id == CANAL_TNA_ID:

            total_match = re.search(
                r"ahora tiene\s+([\d\.,]+)",
                contenido,
                re.IGNORECASE
            )

            if total_match:

                TOTAL_CLAN_TNA = int(
                    total_match.group(1)
                    .replace(".", "")
                    .replace(",", "")
                )

            ejecutar("""
                INSERT INTO puntos_tna (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos = puntos_tna.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            if SEMANA_ACTIVA:
                ejecutar("""
                    INSERT INTO puntos_tna_semanal (usuario, puntos)
                    VALUES (%s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET puntos = puntos_tna_semanal.puntos + EXCLUDED.puntos
                """, (usuario, puntos))

            print("💾 TNA GUARDADO (GENERAL + SEMANAL)")

            await message.channel.send(
                f"✅ {usuario} +{puntos:,} puntos TNA"
            )

    except Exception as e:
        print("❌ ERROR BD:", e)

# =========================
# COMMANDS
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# =========================
# RESET KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    try:
        ejecutar("DELETE FROM puntos_kuro")
        await ctx.send("♻️ KURO reseteado.")

    except Exception as e:
        await ctx.send("❌ Error al resetear KURO.")
        print(e)

# =========================
# RESET TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resettna(ctx):

    try:
        ejecutar("DELETE FROM puntos_tna")
        await ctx.send("♻️ TNA reseteado.")

    except Exception as e:
        await ctx.send("❌ Error al resetear TNA.")
        print(e)

# =========================
# TOP KURO
# =========================

@bot.command()
async def topkuro(ctx):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos en KURO.")
        return

    msg = "🏆 KURO TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    if len(msg) > 1900:

        partes = []
        actual = ""

        for linea in msg.split("\n"):

            if len(actual) + len(linea) > 1900:
                partes.append(actual)
                actual = ""

            actual += linea + "\n"

        partes.append(actual)

        for parte in partes:
            await ctx.send(f"```{parte}```")

    else:
        await ctx.send(f"```{msg}```")

# =========================
# TOP TNA
# =========================

@bot.command()
async def toptna(ctx):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_tna
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos en TNA.")
        return

    msg = "🏆 TNA TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    if len(msg) > 1900:

        partes = []
        actual = ""

        for linea in msg.split("\n"):

            if len(actual) + len(linea) > 1900:
                partes.append(actual)
                actual = ""

            actual += linea + "\n"

        partes.append(actual)

        for parte in partes:
            await ctx.send(f"```{parte}```")

    else:
        await ctx.send(f"```{msg}```")

# =========================
# PUNTOS KURO + POSICIÓN
# =========================

@bot.command()
async def puntoskuro(ctx, usuario: str):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos en KURO.")
        return

    usuario = usuario.lower()

    posicion = None
    puntos = None

    for i, (u, p) in enumerate(data, 1):

        if u == usuario:
            posicion = i
            puntos = p
            break

    if posicion is None:
        await ctx.send("❌ Usuario no encontrado.")
        return

    await ctx.send(
        f"🏆 {usuario} tiene {puntos:,} puntos KURO.\n"
        f"📊 Posición en el top: #{posicion}"
    )

# =========================
# PUNTOS TNA + POSICIÓN
# =========================

@bot.command()
async def puntostna(ctx, usuario: str):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_tna
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos en TNA.")
        return

    usuario = usuario.lower()

    posicion = None
    puntos = None

    for i, (u, p) in enumerate(data, 1):

        if u == usuario:
            posicion = i
            puntos = p
            break

    if posicion is None:
        await ctx.send("❌ Usuario no encontrado.")
        return

    await ctx.send(
        f"🏆 {usuario} tiene {puntos:,} puntos TNA.\n"
        f"📊 Posición en el top: #{posicion}"
    )

# =========================
# TOTAL GENERAL KURO
# =========================

@bot.command()
async def totalkuro(ctx):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT SUM(puntos)
        FROM puntos_kuro
    """, fetch=True)

    total_bd = data[0][0] or 0

    await ctx.send(
        f"🏆 Total sumado KURO: {total_bd:,} puntos.\n"
        f"🌎 Total general del clan: {TOTAL_CLAN_KURO:,} puntos."
    )

# =========================
# TOTAL GENERAL TNA
# =========================

@bot.command()
async def totaltna(ctx):

    if not puede_usar_comando(ctx):

        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )

        return

    data = ejecutar("""
        SELECT SUM(puntos)
        FROM puntos_tna
    """, fetch=True)

    total_bd = data[0][0] or 0

    await ctx.send(
        f"🏆 Total sumado TNA: {total_bd:,} puntos.\n"
        f"🌎 Total general del clan: {TOTAL_CLAN_TNA:,} puntos."
    )

# =========================
# TOP SEMANAL
# =========================

async def enviar_top_semanal(ctx, tabla, titulo):
    data = ejecutar(
        f"SELECT usuario, puntos FROM {tabla} ORDER BY puntos DESC",
        fetch=True
    )

    if not data:
        await ctx.send(f"❌ No hay datos semanales en {titulo}.")
        return

    msg = f"🏆 {titulo} TOP SEMANAL 🏆\n\n"
    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    if len(msg) <= 1900:
        await ctx.send(f"```{msg}```")
        return

    actual = ""
    for linea in msg.splitlines():
        if len(actual) + len(linea) + 1 > 1900:
            await ctx.send(f"```{actual}```")
            actual = ""
        actual += linea + "\n"
    if actual:
        await ctx.send(f"```{actual}```")


@bot.command()
async def topkurosemanal(ctx):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return
    await enviar_top_semanal(ctx, "puntos_kuro_semanal", "KURO")


@bot.command()
async def toptnasemanal(ctx):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return
    await enviar_top_semanal(ctx, "puntos_tna_semanal", "TNA")


@bot.command()
async def puntoskurosemanal(ctx, usuario: str):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos FROM puntos_kuro_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    usuario = usuario.lower()
    for i, (u, p) in enumerate(data, 1):
        if u == usuario:
            await ctx.send(
                f"🏆 {usuario} tiene {p:,} puntos KURO esta semana.\n"
                f"📊 Posición semanal: #{i}"
            )
            return

    await ctx.send("❌ Usuario no encontrado en el ranking semanal KURO.")


@bot.command()
async def puntostnasemanal(ctx, usuario: str):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos FROM puntos_tna_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    usuario = usuario.lower()
    for i, (u, p) in enumerate(data, 1):
        if u == usuario:
            await ctx.send(
                f"🏆 {usuario} tiene {p:,} puntos TNA esta semana.\n"
                f"📊 Posición semanal: #{i}"
            )
            return

    await ctx.send("❌ Usuario no encontrado en el ranking semanal TNA.")


@bot.command()
@commands.has_permissions(administrator=True)
async def resetsemanal(ctx):
    try:
        ejecutar("DELETE FROM puntos_kuro_semanal")
        ejecutar("DELETE FROM puntos_tna_semanal")

        fin = calcular_fin_semana()
        inicio = fin - timedelta(days=7) + timedelta(microseconds=1)

        ejecutar("""
            INSERT INTO estado_semanal (id, inicio, fin)
            VALUES (1, %s, %s)
            ON CONFLICT (id)
            DO UPDATE SET inicio = EXCLUDED.inicio, fin = EXCLUDED.fin
        """, (inicio, fin))

        await ctx.send("♻️ Puntuaciones semanales de KURO y TNA reiniciadas.")
    except Exception as e:
        await ctx.send("❌ Error al reiniciar las puntuaciones semanales.")
        print("❌ ERROR RESET SEMANAL:", e)


@bot.command()
async def semanainfo(ctx):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    inicio, fin = inicializar_periodo_semanal()
    restante = max(fin - datetime.now(TZ), timedelta(0))
    dias = restante.days
    horas, resto = divmod(restante.seconds, 3600)
    minutos = resto // 60

    await ctx.send(
        "📅 **SEMANA ACTUAL**\n"
        f"🟢 Inicio: {inicio.strftime('%d/%m/%Y %H:%M')}\n"
        f"🔴 Finaliza: {fin.strftime('%d/%m/%Y %H:%M')}\n"
        f"⏳ Tiempo restante: {dias}d {horas}h {minutos}m"
    )

# =========================
# ACTIVAR / DESACTIVAR SEMANAL
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def activarsemanal(ctx):
    global SEMANA_ACTIVA
    SEMANA_ACTIVA = True
    inicializar_periodo_semanal()
    await ctx.send("✅ Sistema de puntos semanal **ACTIVADO**.")


@bot.command()
@commands.has_permissions(administrator=True)
async def desactivarsemanal(ctx):
    global SEMANA_ACTIVA
    SEMANA_ACTIVA = False
    await ctx.send(
        "⏸️ Sistema de puntos semanal **DESACTIVADO**. "
        "Los puntos generales seguirán funcionando normalmente."
    )


# =========================
# CONFIGURAR TABLA FINAL
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def tablasemanalfinal(ctx, opcion: str):
    global TABLAS_AL_FINALIZAR

    opcion = opcion.lower().strip()

    opciones = {
        "kuro": "kuro",
        "tna": "tna",
        "ambas": "ambas",
    }

    if opcion not in opciones:
        await ctx.send(
            "❌ Opción inválida. Usa:\n"
            "`!tablasemanalfinal kuro` → solo KURO\n"
            "`!tablasemanalfinal tna` → solo TNA\n"
            "`!tablasemanalfinal ambas` → KURO + TNA"
        )
        return

    TABLAS_AL_FINALIZAR = opciones[opcion]

    await ctx.send(
        f"✅ Tabla(s) al finalizar configuradas: **{TABLAS_AL_FINALIZAR.upper()}**"
    )


@bot.command()
async def configsemanal(ctx):
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    estado = "ACTIVADO" if SEMANA_ACTIVA else "DESACTIVADO"

    await ctx.send(
        "⚙️ **CONFIGURACIÓN SEMANAL**\n"
        f"Estado: **{estado}**\n"
        f"Tabla(s) al finalizar: **{TABLAS_AL_FINALIZAR.upper()}**"
    )


# =========================
# SIMULACIÓN KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def simkuro(ctx):

    mensaje = """Informe del clan Kuro
¡El clan Kuro ahora tiene 16,430,437 puntos de experiencia! Rosa_Melano ha conseguido 100.000 puntos para este clan

play.minelatino.com | Información del clan Kuro"""

    await ctx.send(mensaje)

# =========================
# SIMULACIÓN TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def simtna(ctx):

    mensaje = """Informe del clan TNA
¡El clan TNA ahora tiene 8,000,000 puntos de experiencia! Rosa_Melano ha conseguido 50.000 puntos para este clan

play.minelatino.com | Información del clan TNA"""

    await ctx.send(mensaje)

# =========================
# RUN
# =========================

bot.run(TOKEN)
