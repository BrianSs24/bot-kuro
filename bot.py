import discord
from discord.ext import commands
import psycopg2
import re
import os

# =========================
# CONFIGURACIÓN
# =========================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ⚠️ REEMPLAZA ESTO POR EL ID REAL DEL CANAL KURO
CANAL_KURO_ID = 1331359760414539791

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

conexion = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT DEFAULT 0
)
""")

conexion.commit()

# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# =========================
# ON MESSAGE
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        await bot.process_commands(message)
        return

    # =========================
    # SOLO CANAL KURO
    # =========================

    if message.channel.id != CANAL_KURO_ID:
        await bot.process_commands(message)
        return

    # =========================
    # CONSTRUIR CONTENIDO COMPLETO
    # =========================

    contenido = message.content or ""

    if message.embeds:
        for embed in message.embeds:

            if embed.description:
                contenido += " " + embed.description

            if embed.fields:
                for field in embed.fields:
                    contenido += f" {field.name} {field.value}"

    contenido = contenido.strip()

    print("\n====================")
    print("📩 MENSAJE DETECTADO")
    print("CONTENIDO:", contenido)

    # =========================
    # 1. EXTRAER TEXTO ENTRE PARÉNTESIS
    # =========================

    match_par = re.search(r"\((.*?)\)", contenido)

    if not match_par:
        print("❌ No se encontró bloque del clan")
        await bot.process_commands(message)
        return

    bloque = match_par.group(1)

    print("📦 BLOQUE:", bloque)

    # =========================
    # 2. EXTRAER USUARIO Y PUNTOS
    # =========================

    match = re.search(
        r"([\w\d_]+)\s+ha\s+conseguido\s+([\d\.,]+)",
        bloque
    )

    if not match:
        print("❌ No se pudo extraer usuario/puntos")
        await bot.process_commands(message)
        return

    usuario = match.group(1).strip().lower()
    puntos = int(match.group(2).replace(".", "").replace(",", ""))

    print("✔ USUARIO:", usuario)
    print("⭐ PUNTOS:", puntos)

    # =========================
    # GUARDAR EN BD (UPSERT)
    # =========================

    try:
        cursor.execute("""
            INSERT INTO puntos_kuro (usuario, puntos)
            VALUES (%s, %s)
            ON CONFLICT (usuario)
            DO UPDATE SET puntos = puntos_kuro.puntos + EXCLUDED.puntos
        """, (usuario, puntos))

        conexion.commit()

        print("💾 GUARDADO EN BASE DE DATOS")

        await message.channel.send(
            f"✅ {usuario} sumó {puntos:,} puntos en KURO."
        )

    except Exception as e:
        print("❌ ERROR BD:", e)

    await bot.process_commands(message)

# =========================
# COMANDO TEST
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# =========================
# INICIAR BOT
# =========================

bot.run(TOKEN)