import discord
from discord.ext import commands
import psycopg2
import re
import os

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

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# =========================
# EXTRAER DATOS
# =========================

def extraer_datos(texto):

    match_nuevo = re.search(
        r"\(([A-Za-z0-9_]+)\s+\+([\d\.,]+)\s+XP",
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

    match_parentesis = re.search(r"\((.*?)\)", texto)

    if match_parentesis:
        texto = match_parentesis.group(1)

    match = re.search(
        r"([\w\d_]+)\s+ha\s+conseguido\s+([\d\.,]+)",
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

            print("💾 KURO GUARDADO")

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

            print("💾 TNA GUARDADO")

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
