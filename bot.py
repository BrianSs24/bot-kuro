import discord
from discord.ext import commands
import psycopg2
import re

import os

TOKEN = os.getenv("TOKEN")

CANAL_REGISTRO = "registro-kuro"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# BASE DE DATOS POSTGRESQL
# =========================

conexion = psycopg2.connect(
    os.getenv("DATABASE_URL")
)

cursor = conexion.cursor()

# =========================
# CREAR TABLA
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS puntos (
    usuario TEXT PRIMARY KEY,
    puntos INTEGER
)
""")

conexion.commit()

# =========================
# CONFIGURAR BOT
# =========================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# BOT LISTO
# =========================

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

# =========================
# DETECTAR INFORMES
# =========================

@bot.event
async def on_message(message):

    # Ignorar mensajes que no sean del bot de MineLatino
    if message.author.name != "Ultimate Clans V7":
        return

    # Verificar canal
    if message.channel.name != CANAL_REGISTRO:
        return

    contenido = message.content

    # Buscar nombre y puntos
    patron = r"\((.*?) ha conseguido ([\d\.]+) puntos para este clan\)"

    resultado = re.search(patron, contenido)

    if resultado:

        usuario = resultado.group(1)

        puntos = resultado.group(2)
        puntos = puntos.replace(".", "")
        puntos = int(puntos)

        # Verificar si ya existe
        cursor.execute(
            "SELECT puntos FROM puntos WHERE usuario = ?",
            (usuario,)
        )

        fila = cursor.fetchone()

        if fila:
            nuevos_puntos = fila[0] + puntos

            cursor.execute(
                "UPDATE puntos SET puntos = ? WHERE usuario = ?",
                (nuevos_puntos, usuario)
            )

        else:
            cursor.execute(
                "INSERT INTO puntos(usuario, puntos) VALUES(?, ?)",
                (usuario, puntos)
            )

        conexion.commit()

        await message.channel.send(
            f"✅ {usuario} sumó {puntos:,} puntos al registro Kuro."
        )

    await bot.process_commands(message)

# =========================
# VER RANKING
# =========================

@bot.command()
async def topkuro(ctx):

    cursor.execute(
        "SELECT usuario, puntos FROM puntos ORDER BY puntos DESC"
    )

    datos = cursor.fetchall()

    if not datos:
        await ctx.send("No hay puntos registrados.")
        return

    mensaje = "🏆 Ranking del Clan Kuro 🏆\n\n"

    posicion = 1

    for usuario, puntos in datos:

        mensaje += (
            f"{posicion}. {usuario} → {puntos:,} puntos\n"
        )

        posicion += 1

    await ctx.send(f"```{mensaje}```")

# =========================
# VER PUNTOS INDIVIDUALES
# =========================

@bot.command()
async def puntos(ctx, usuario):

    cursor.execute(
        "SELECT puntos FROM puntos WHERE usuario = ?",
        (usuario,)
    )

    resultado = cursor.fetchone()

    if resultado:

        await ctx.send(
            f"📊 {usuario} tiene {resultado[0]:,} puntos."
        )

    else:
        await ctx.send("Ese usuario no existe.")

# =========================
# REINICIAR TABLA
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def resetkuro(ctx):

    cursor.execute("DELETE FROM puntos")

    conexion.commit()

    await ctx.send(
        "♻️ La tabla de puntos fue reiniciada correctamente."
    )

# =========================
# ELIMINAR USUARIO
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def borrarusuario(ctx, usuario):

    cursor.execute(
        "DELETE FROM puntos WHERE usuario = ?",
        (usuario,)
    )

    conexion.commit()

    await ctx.send(
        f"🗑️ Usuario {usuario} eliminado."
    )

# =========================
# EJECUTAR BOT
# =========================

bot.run(TOKEN)