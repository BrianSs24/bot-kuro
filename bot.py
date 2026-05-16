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

# =========================
# BOTS MINELATINO PERMITIDOS
# =========================

MINELATINO_BOTS = [
    1331382760094306355,  # Bot 1 (cámbialo)
    1331382760094306355   # Bot 2 (cámbialo)
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
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DB (SIN CURSOR GLOBAL)
# =========================

def ejecutar(query, params=None):
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    cur.execute(query, params)

    conn.commit()
    cur.close()
    conn.close()

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
# MESSAGE EVENT (2 BOTS)
# =========================

@bot.event
async def on_message(message):

    # ❌ SOLO bots MineLatino permitidos
    if message.author.id not in MINELATINO_BOTS:
        return

    # SOLO canal KURO
    if message.channel.id != CANAL_KURO_ID:
        return

    contenido = message.content or ""

    for embed in message.embeds:
        if embed.description:
            contenido += " " + embed.description

    print("\n====================")
    print("📩 MENSAJE MINELATINO DETECTADO")
    print("CONTENIDO:", contenido)

    usuario, puntos = extraer_datos(contenido)

    if not usuario:
        print("❌ NO SE PUDO EXTRAER DATA")
        return

    print("✔ USUARIO:", usuario)
    print("⭐ PUNTOS:", puntos)

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

# 🔐 TOP SOLO ROLES
@bot.command()
@commands.check(tiene_permiso)
async def topkuro(ctx):

    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cur = conn.cursor()

    cur.execute("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    msg = "🏆 KURO TOP 🏆\n\n"

    for i, (u, p) in enumerate(data, 1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# RUN
# =========================

bot.run(TOKEN)