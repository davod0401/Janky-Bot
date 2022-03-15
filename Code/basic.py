import discord

client = discord.Client()

@client.event
async def on_ready():
    print('Conectado como {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.startswith('*'):
        mensaje = message.content.split('*')
        await message.channel.send('Dijiste: ' + mensaje[1])

client.run('TOKEN') #Token del bot
