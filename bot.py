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
# BOTS MINELATINO
# =========================

MINELATINO_BOTS = [
    1331382760094306355
]

# =========================
# ROLES PRINCIPALES
# =========================

ALLOWED_ROLES = [
    935248281980796948,
    920144442843885639,
    1157136068613767268
]

def tiene_permiso(ctx):
    return any(role.id in ALLOWED_ROLES for role in ctx.author.roles)

# =========================
# VALIDAR CANAL CMD
# =========================

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
    puntos = int(match.group(2).replace(".", "").replace(",", ""))

    return usuario, puntos

# =========================
# MESSAGE EVENT
# =========================

@bot.event
async def on_message(message):

    # Ignorar bots no autorizados
    if message.author.bot and message.author.id not in MINELATINO_BOTS:
        return

    # =========================
    # SOLO MINELATINO
    # =========================

    if message.author.id in MINELATINO_BOTS:

        contenido = message.content or ""

        for embed in message.embeds:
            if embed.description:
                contenido += " " + embed.description

        print("\n====================")
        print("📩 MENSAJE MINELATINO DETECTADO")
        print("CONTENIDO:", contenido)

        usuario, puntos = extraer_datos(contenido)

        if usuario:

            try:

                # =========================
                # KURO
                # =========================

                if message.channel.id == CANAL_KURO_ID:

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

    await bot.process_commands(message)

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
        LIMIT 20
    """, fetch=True)

    msg = "🏆 KURO TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

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
        LIMIT 20
    """, fetch=True)

    msg = "🏆 TNA TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# PUNTOS KURO
# =========================

@bot.command()
async def puntoskuro(ctx, usuario: str):

    if not puede_usar_comando(ctx):
        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )
        return

    data = ejecutar("""
        SELECT puntos
        FROM puntos_kuro
        WHERE usuario = %s
    """, (usuario.lower(),), fetch=True)

    if not data:
        await ctx.send("❌ Usuario no encontrado.")
        return

    puntos = data[0][0]

    await ctx.send(
        f"🏆 {usuario} tiene {puntos:,} puntos KURO."
    )

# =========================
# PUNTOS TNA
# =========================

@bot.command()
async def puntostna(ctx, usuario: str):

    if not puede_usar_comando(ctx):
        await ctx.send(
            "❌ Solo puedes usar este comando en 『🤖』cmd."
        )
        return

    data = ejecutar("""
        SELECT puntos
        FROM puntos_tna
        WHERE usuario = %s
    """, (usuario.lower(),), fetch=True)

    if not data:
        await ctx.send("❌ Usuario no encontrado.")
        return

    puntos = data[0][0]

    await ctx.send(
        f"🏆 {usuario} tiene {puntos:,} puntos TNA."
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

    class FakeAuthor:
        def __init__(self):
            self.bot = True
            self.id = MINELATINO_BOTS[0]

    class FakeChannel:
        def __init__(self, real_channel):
            self.id = CANAL_KURO_ID
            self.real_channel = real_channel

        async def send(self, content):
            await self.real_channel.send(content)

    class FakeMessage:
        def __init__(self):
            self.author = FakeAuthor()
            self.channel = FakeChannel(ctx.channel)
            self.content = mensaje
            self.embeds = []

    fake = FakeMessage()

    # Enviar mensaje tipo MineLatino
    await ctx.send(mensaje)

    # Procesar mensaje
    await on_message(fake)

# =========================
# SIMULACIÓN TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def simtna(ctx):

    mensaje = """Informe del clan TNA
¡El clan TNA ahora tiene 8,000,000 puntos de experiencia! Rosa_Melano ha conseguido 50.000 puntos para este clan

play.minelatino.com | Información del clan TNA"""

    class FakeAuthor:
        def __init__(self):
            self.bot = True
            self.id = MINELATINO_BOTS[0]

    class FakeChannel:
        def __init__(self, real_channel):
            self.id = CANAL_TNA_ID
            self.real_channel = real_channel

        async def send(self, content):
            await self.real_channel.send(content)

    class FakeMessage:
        def __init__(self):
            self.author = FakeAuthor()
            self.channel = FakeChannel(ctx.channel)
            self.content = mensaje
            self.embeds = []

    fake = FakeMessage()

    # Enviar mensaje tipo MineLatino
    await ctx.send(mensaje)

    # Procesar mensaje
    await on_message(fake)

# =========================
# RUN
# =========================

bot.run(TOKEN)