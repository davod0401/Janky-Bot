import discord

class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))

client = MyClient()
client.run('OTUyNzc3MTE0MTA3NjU0MTU0.Yi681Q.vBrDOr1IxgGdnx_CE0mKzcV3wIU')