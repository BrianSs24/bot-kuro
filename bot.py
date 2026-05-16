import discord
from discord.ext import commands
import psycopg2
import re
import os

# =========================
# VARIABLES
# =========================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

CANAL_KURO = "registro-kuro"
CANAL_TNA = "registro-tna"

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

conexion = psycopg2.connect(DATABASE_URL)
cursor = conexion.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_kuro (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos_tna (
    usuario TEXT PRIMARY KEY,
    puntos BIGINT
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
    # CONSTRUIR TEXTO COMPLETO
    # =========================

    contenido = ""

    if message.content:
        contenido += message.content

    if message.embeds:
        for embed in message.embeds:

            if embed.description:
                contenido += " " + embed.description

            if embed.fields:
                for field in embed.fields:
                    contenido += f" {field.name} {field.value}"

    contenido = contenido.strip()

    # DEBUG (puedes quitarlo luego)
    print("📩 CONTENIDO DETECTADO:", contenido)

    # =========================
    # REGEX ROBUSTO
    # =========================

    patron = r"([\w\W]+?)\s+ha\s+conseguido\s+([\d\.,]+)\s+puntos"
    resultado = re.search(patron, contenido, re.IGNORECASE)

    if resultado:

        usuario = resultado.group(1).strip()

        # =========================
        # NORMALIZAR NÚMEROS
        # =========================

        puntos_raw = resultado.group(2)

        puntos = puntos_raw.replace(".", "").replace(",", "")
        puntos = int(puntos)

        print(f"🎯 MATCH: {usuario} + {puntos}")

        # =========================
        # KURO
        # =========================

        if message.channel.name == CANAL_KURO:

            cursor.execute(
                "SELECT puntos FROM puntos_kuro WHERE usuario = %s",
                (usuario,)
            )

            fila = cursor.fetchone()

            if fila:
                nuevos = fila[0] + puntos
                cursor.execute(
                    "UPDATE puntos_kuro SET puntos = %s WHERE usuario = %s",
                    (nuevos, usuario)
                )
            else:
                cursor.execute(
                    "INSERT INTO puntos_kuro(usuario, puntos) VALUES(%s, %s)",
                    (usuario, puntos)
                )

            conexion.commit()

            await message.channel.send(
                f"✅ {usuario} sumó {puntos:,} puntos en KURO."
            )

        # =========================
        # TNA
        # =========================

        elif message.channel.name == CANAL_TNA:

            cursor.execute(
                "SELECT puntos FROM puntos_tna WHERE usuario = %s",
                (usuario,)
            )

            fila = cursor.fetchone()

            if fila:
                nuevos = fila[0] + puntos
                cursor.execute(
                    "UPDATE puntos_tna SET puntos = %s WHERE usuario = %s",
                    (nuevos, usuario)
                )
            else:
                cursor.execute(
                    "INSERT INTO puntos_tna(usuario, puntos) VALUES(%s, %s)",
                    (usuario, puntos)
                )

            conexion.commit()

            await message.channel.send(
                f"✅ {usuario} sumó {puntos:,} puntos en TNA."
            )

    await bot.process_commands(message)

# =========================
# TOP KURO
# =========================

@bot.command()
async def topkuro(ctx):

    cursor.execute("SELECT usuario, puntos FROM puntos_kuro ORDER BY puntos DESC")
    datos = cursor.fetchall()

    if not datos:
        return await ctx.send("No hay puntos en KURO.")

    msg = "🏆 RANKING KURO 🏆\n\n"

    for i, (u, p) in enumerate(datos, start=1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# PUNTOS KURO
# =========================

@bot.command()
async def puntoskuro(ctx, *, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    res = cursor.fetchone()

    if res:
        await ctx.send(f"📊 {usuario} tiene {res[0]:,} puntos en KURO.")
    else:
        await ctx.send("Usuario no encontrado en KURO.")

# =========================
# RESET KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    cursor.execute("DELETE FROM puntos_kuro")
    conexion.commit()

    await ctx.send("♻️ KURO reiniciado.")

# =========================
# BORRAR USUARIO KURO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuariokuro(ctx, *, usuario):

    cursor.execute(
        "DELETE FROM puntos_kuro WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(f"🗑️ {usuario} eliminado de KURO.")

# =========================
# TOP TNA
# =========================

@bot.command()
async def toptna(ctx):

    cursor.execute("SELECT usuario, puntos FROM puntos_tna ORDER BY puntos DESC")
    datos = cursor.fetchall()

    if not datos:
        return await ctx.send("No hay puntos en TNA.")

    msg = "🏆 RANKING TNA 🏆\n\n"

    for i, (u, p) in enumerate(datos, start=1):
        msg += f"{i}. {u} → {p:,}\n"

    await ctx.send(f"```{msg}```")

# =========================
# PUNTOS TNA
# =========================

@bot.command()
async def puntostna(ctx, *, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos_tna WHERE usuario = %s",
        (usuario,)
    )

    res = cursor.fetchone()

    if res:
        await ctx.send(f"📊 {usuario} tiene {res[0]:,} puntos en TNA.")
    else:
        await ctx.send("Usuario no encontrado en TNA.")

# =========================
# RESET TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resettna(ctx):

    cursor.execute("DELETE FROM puntos_tna")
    conexion.commit()

    await ctx.send("♻️ TNA reiniciado.")

# =========================
# BORRAR USUARIO TNA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuariotna(ctx, *, usuario):

    cursor.execute(
        "DELETE FROM puntos_tna WHERE usuario = %s",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(f"🗑️ {usuario} eliminado de TNA.")

# =========================
# PING
# =========================

@bot.command()
async def ping(ctx):
    await ctx.send("pong")

# =========================
# RUN BOT
# =========================

bot.run(TOKEN)