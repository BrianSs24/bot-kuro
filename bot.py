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

CANAL_KURO_ID = 1331359760414539791
CANAL_CMD_ID = 1278916162117177385

# =========================
# BOTS MINELATINO PERMITIDOS
# =========================

MINELATINO_BOTS = [
    1331382760094306355
]

# =========================
# ROLES PERMITIDOS
# =========================

ALLOWED_ROLES = [
    935248281980796948,
    920144442843885639
]

def tiene_permiso(ctx):
    return any(role.id in ALLOWED_ROLES for role in ctx.author.roles)

# =========================
# VERIFICAR CANAL CMD
# =========================

def canal_cmd(ctx):
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
# CREAR TABLA
# =========================

ejecutar("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
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
# EXTRACTOR
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

    # ❌ ignorar bots no autorizados
    if message.author.bot and message.author.id not in MINELATINO_BOTS:
        return

    # =========================
    # SOLO MINELATINO REAL
    # =========================
    if message.author.id in MINELATINO_BOTS and message.channel.id == CANAL_KURO_ID:

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
                ejecutar("""
                    INSERT INTO puntos_kuro (usuario, puntos)
                    VALUES (%s, %s)
                    ON CONFLICT (usuario)
                    DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
                """, (usuario, puntos))

                print("💾 GUARDADO OK")

                await message.channel.send(
                    f"✅ {usuario} +{puntos:,} puntos KURO"
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

# 🔐 RESET SOLO ADMIN
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
# TOP KURO
# TODOS LOS USUARIOS
# SOLO EN CANAL CMD
# =========================

@bot.command()
@commands.check(canal_cmd)
async def topkuro(ctx):

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
# PUNTOS INDIVIDUALES
# =========================

@bot.command()
@commands.check(canal_cmd)
async def puntoskuro(ctx, usuario: str):

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
# SIMULACIÓN MINELATINO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def simkuro(ctx):

    mensaje = """Informe del clan Kuro
¡El clan Kuro ahora tiene 16,430,437 puntos de experiencia! Crasty22 ha conseguido 100.000 puntos para este clan

play.minelatino.com | Información del clan Kuro"""

    class FakeAuthor:
        def __init__(self):
            self.bot = True
            self.id = MINELATINO_BOTS[0]

    class FakeChannel:
        def __init__(self):
            self.id = CANAL_KURO_ID

        async def send(self, content):
            print("📤 SIMULACIÓN ENVÍO:", content)

    class FakeMessage:
        def __init__(self):
            self.author = FakeAuthor()
            self.channel = FakeChannel()
            self.content = mensaje
            self.embeds = []

    fake = FakeMessage()

    await on_message(fake)

    await ctx.send("🧪 Simulación de MineLatino ejecutada")

# =========================
# RUN
# =========================

bot.run(TOKEN)