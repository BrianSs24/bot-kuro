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

# ⚠️ IMPORTANTE: usa el ID del canal KURO (RECOMENDADO)
# reemplázalo con el tuyo real
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

    # ignorar bots
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
    # CONSTRUIR CONTENIDO
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
    print("📩 MENSAJE KURO DETECTADO")
    print("CONTENIDO:", contenido)

    # =========================
    # REGEX
    # =========================

    patron = r"([\w\W]+?)\s+ha\s+conseguido\s+([\d\.,]+)\s+puntos"
    resultado = re.search(patron, contenido, re.IGNORECASE)

    if not resultado:
        print("❌ NO MATCH REGEX")
        await bot.process_commands(message)
        return

    usuario = resultado.group(1).strip().lower()
    puntos = int(resultado.group(2).replace(".", "").replace(",", ""))

    print("✔ MATCH OK")
    print("👤 USUARIO:", usuario)
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

        print("💾 GUARDADO EN KURO OK")

        await message.channel.send(
            f"✅ {usuario} sumó {puntos:,} puntos en KURO."
        )

    except Exception as e:
        print("❌ ERROR BD:", e)

    await bot.process_commands(message)

# =========================
# COMANDOS
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

@bot.command()
async def topkuro(ctx):

    cursor.execute("""
        SELECT usuario, puntos
        FROM puntos_kuro
        ORDER BY puntos DESC
    """)

    datos = cursor.fetchall()

    if not datos:
        return await ctx.send("No hay puntos en KURO.")

    msg = "🏆 RANKING KURO 🏆\n\n"

    for i, (u, p) in enumerate(datos, start=1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

@bot.command()
async def puntoskuro(ctx, *, usuario):

    usuario = usuario.strip().lower()

    cursor.execute(
        "SELECT puntos FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    res = cursor.fetchone()

    if res:
        await ctx.send(f"📊 {usuario} tiene {res[0]:,} puntos en KURO.")
    else:
        await ctx.send("Usuario no encontrado en KURO.")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    cursor.execute("DELETE FROM puntos_kuro")
    conexion.commit()

    await ctx.send("♻️ KURO reiniciado.")

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuariokuro(ctx, *, usuario):

    usuario = usuario.strip().lower()

    cursor.execute(
        "DELETE FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(f"🗑️ {usuario} eliminado de KURO.")

# =========================
# RUN BOT
# =========================

bot.run(TOKEN)