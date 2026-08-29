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

# Nombre exacto / parcial de los bots permitidos
BOTS_PERMITIDOS = [
    "MineLatino",
    "Ultimate Clans V7"
]

# Roles principales
ALLOWED_ROLES = [
    935248281980796948,
    920144442843885639,
    1157136068613767268
]

# =========================
# SISTEMA SEMANAL
# =========================

SEMANA_ACTIVA = True

# Opciones: "tna", "kuro", "ambas"
TABLAS_AL_FINALIZAR = "tna"

TZ = ZoneInfo("America/Santo_Domingo")

# Domingo 23:59:59 hora RD
DIA_FIN_SEMANA = 6
HORA_FIN_SEMANA = 23
MINUTO_FIN_SEMANA = 59

# =========================
# TOTALES GENERALES
# =========================

TOTAL_CLAN_KURO = 0
TOTAL_CLAN_TNA = 0

# =========================
# PERMISOS
# =========================

def tiene_permiso(ctx):
    return any(role.id in ALLOWED_ROLES for role in ctx.author.roles)


def puede_usar_comando(ctx):
    if tiene_permiso(ctx):
        return True
    return ctx.channel.id == CANAL_CMD_ID


# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# BASE DE DATOS
# =========================

def ejecutar(query, params=None, fetch=False):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está configurada.")

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    try:
        cur.execute(query, params)
        data = cur.fetchall() if fetch else None
        conn.commit()
        return data
    finally:
        cur.close()
        conn.close()


def crear_tablas():
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

    # Python: lunes=0 ... domingo=6
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


def construir_top(titulo, data):
    texto = f"🏆 **{titulo}**\n\n"

    if not data:
        return texto + "No hubo puntos registrados esta semana.\n"

    for i, (usuario, puntos) in enumerate(data, 1):
        texto += f"{i}. {usuario} → {puntos:,}\n"

    return texto


async def enviar_bloque(canal, texto):
    if len(texto) <= 1900:
        await canal.send(texto)
        return

    actual = ""

    for linea in texto.splitlines():
        if len(actual) + len(linea) + 1 > 1900:
            if actual:
                await canal.send(actual)
            actual = ""

        actual += linea + "\n"

    if actual:
        await canal.send(actual)


async def comprobar_cierre_semanal():
    if not SEMANA_ACTIVA:
        return

    ahora = datetime.now(TZ)
    inicio, fin = inicializar_periodo_semanal()

    if ahora < fin:
        return

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
        print(
            f"⚠️ TABLAS_AL_FINALIZAR='{TABLAS_AL_FINALIZAR}' inválido. "
            "Se usará TNA."
        )
        bloques = [construir_top("TNA — TOP SEMANAL", tna)]

    encabezado = (
        "🏁 **TABLA DE PUNTOS SEMANAL FINALIZADA** 🏁\n\n"
        "La acumulación de puntos de esta semana ha terminado."
    )

    pie = "♻️ Las puntuaciones semanales serán reiniciadas ahora."

    for canal_id in (CANAL_KURO_ID, CANAL_TNA_ID):
        canal = bot.get_channel(canal_id)

        if not canal:
            print(f"⚠️ No se encontró el canal {canal_id}.")
            continue

        try:
            await enviar_bloque(canal, encabezado)

            for bloque in bloques:
                await enviar_bloque(canal, bloque)

            await enviar_bloque(canal, pie)

        except Exception as e:
            print("❌ ERROR ENVIANDO TOP SEMANAL FINAL:", e)

    # Se borran únicamente las tablas semanales.
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

    try:
        inicializar_periodo_semanal()
    except Exception as e:
        print("❌ ERROR INICIALIZANDO SEMANA:", e)


# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

    try:
        crear_tablas()
        inicializar_periodo_semanal()
    except Exception as e:
        print("❌ ERROR INICIALIZANDO BASE DE DATOS:", e)
        return

    if not revisar_semana.is_running():
        revisar_semana.start()


# =========================
# EXTRAER DATOS
# =========================

def extraer_datos(texto):
    # Formato nuevo:
    # (usuario +10000 XP | Total: ...)
    match_nuevo = re.search(
        r"\(([A-Za-z0-9_.]+)\s+\+([\d\.,]+)\s+XP",
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

    # Formato anterior:
    # usuario ha conseguido 100.000 puntos...
    match = re.search(
        r"([\w\d_.]+)\s+ha\s+conseguido\s+([\d\.,]+)",
        texto,
        re.IGNORECASE
    )

    if not match:
        return None, None

    usuario = match.group(1).lower()

    puntos = int(
        match.group(2)
        .replace(".", "")
        .replace(",", "")
    )

    return usuario, puntos


# =========================
# MENSAJES
# =========================

@bot.event
async def on_message(message):
    global TOTAL_CLAN_KURO
    global TOTAL_CLAN_TNA

    await bot.process_commands(message)

    if not message.author.bot:
        return

    bot_valido = any(
        nombre.lower() in message.author.name.lower()
        for nombre in BOTS_PERMITIDOS
    )

    if not bot_valido:
        return

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

            # GENERAL
            ejecutar("""
                INSERT INTO puntos_kuro (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos =
                    puntos_kuro.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            # SEMANAL
            if SEMANA_ACTIVA:
                ejecutar("""
                    INSERT INTO puntos_kuro_semanal (usuario, puntos)
                    VALUES (%s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET puntos =
                        puntos_kuro_semanal.puntos + EXCLUDED.puntos
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

            # GENERAL
            ejecutar("""
                INSERT INTO puntos_tna (usuario, puntos)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET puntos =
                    puntos_tna.puntos + EXCLUDED.puntos
            """, (usuario, puntos))

            # SEMANAL
            if SEMANA_ACTIVA:
                ejecutar("""
                    INSERT INTO puntos_tna_semanal (usuario, puntos)
                    VALUES (%s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET puntos =
                        puntos_tna_semanal.puntos + EXCLUDED.puntos
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
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
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

    await enviar_bloque(ctx.channel, f"```{msg}```")


# =========================
# TOP TNA
# =========================

@bot.command()
async def toptna(ctx):
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
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

    await enviar_bloque(ctx.channel, f"```{msg}```")


# =========================
# PUNTOS KURO
# =========================

@bot.command()
async def puntoskuro(ctx, usuario: str):
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """, fetch=True)

    usuario = usuario.lower()

    for i, (u, p) in enumerate(data, 1):
        if u == usuario:
            await ctx.send(
                f"🏆 {usuario} tiene {p:,} puntos KURO.\n"
                f"📊 Posición en el top: #{i}"
            )
            return

    await ctx.send("❌ Usuario no encontrado.")


# =========================
# PUNTOS TNA
# =========================

@bot.command()
async def puntostna(ctx, usuario: str):
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_tna
        ORDER BY puntos DESC
    """, fetch=True)

    usuario = usuario.lower()

    for i, (u, p) in enumerate(data, 1):
        if u == usuario:
            await ctx.send(
                f"🏆 {usuario} tiene {p:,} puntos TNA.\n"
                f"📊 Posición en el top: #{i}"
            )
            return

    await ctx.send("❌ Usuario no encontrado.")


# =========================
# TOTAL GENERAL KURO
# =========================

@bot.command()
async def totalkuro(ctx):
    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
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
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
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

@bot.command()
async def topkurosemanal(ctx):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return

    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos semanales en KURO.")
        return

    msg = "🏆 KURO TOP SEMANAL 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await enviar_bloque(ctx.channel, f"```{msg}```")


@bot.command()
async def toptnasemanal(ctx):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return

    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_tna_semanal
        ORDER BY puntos DESC
    """, fetch=True)

    if not data:
        await ctx.send("❌ No hay datos semanales en TNA.")
        return

    msg = "🏆 TNA TOP SEMANAL 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await enviar_bloque(ctx.channel, f"```{msg}```")


# =========================
# PUNTOS SEMANALES
# =========================

@bot.command()
async def puntoskurosemanal(ctx, usuario: str):
    if not SEMANA_ACTIVA:
        await ctx.send("⚠️ El sistema de puntos semanal está desactivado.")
        return

    if not puede_usar_comando(ctx):
        await ctx.send("❌ Solo puedes usar este comando en 『🤖』cmd.")
        return

    data = ejecutar("""
        SELECT usuario, puntos
        FROM puntos_kuro_semanal
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
        SELECT usuario, puntos
        FROM puntos_tna_semanal
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


# =========================
# RESET SEMANAL
# =========================

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
            DO UPDATE SET
                inicio = EXCLUDED.inicio,
                fin = EXCLUDED.fin
        """, (inicio, fin))

        await ctx.send(
            "♻️ Puntuaciones semanales de KURO y TNA reiniciadas."
        )

    except Exception as e:
        await ctx.send(
            "❌ Error al reiniciar las puntuaciones semanales."
        )
        print("❌ ERROR RESET SEMANAL:", e)


# =========================
# ACTIVAR / DESACTIVAR
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
# TABLA FINAL
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def tablasemanalfinal(ctx, opcion: str):
    global TABLAS_AL_FINALIZAR

    opcion = opcion.lower().strip()

    if opcion not in ("kuro", "tna", "ambas"):
        await ctx.send(
            "❌ Opción inválida.\n\n"
            "`!tablasemanalfinal kuro` → solo KURO\n"
            "`!tablasemanalfinal tna` → solo TNA\n"
            "`!tablasemanalfinal ambas` → KURO + TNA"
        )
        return

    TABLAS_AL_FINALIZAR = opcion

    await ctx.send(
        f"✅ Tabla(s) al finalizar configuradas: "
        f"**{TABLAS_AL_FINALIZAR.upper()}**"
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
# SIMULACIONES
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def simkuro(ctx):
    mensaje = """Informe del clan Kuro
¡El clan Kuro ahora tiene 16,430,437 puntos de experiencia! Rosa_Melano ha conseguido 100.000 puntos para este clan

play.minelatino.com | Información del clan Kuro"""

    await ctx.send(mensaje)


@bot.command()
@commands.has_permissions(administrator=True)
async def simtna(ctx):
    mensaje = """Informe del clan TNA
¡El clan TNA ahora tiene 8,000,000 puntos de experiencia! Rosa_Melano ha conseguido 50.000 puntos para este clan

play.minelatino.com | Información del clan TNA"""

    await ctx.send(mensaje)


# =========================
# ERRORES DE COMANDOS
# =========================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para usar este comando.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Falta un argumento. Revisa el comando.")
        return

    print("❌ ERROR COMANDO:", repr(error))


# =========================
# RUN
# =========================

if not TOKEN:
    raise RuntimeError("TOKEN no está configurado.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está configurada.")

bot.run(TOKEN)
