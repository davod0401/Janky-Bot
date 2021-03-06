# -*- coding: utf-8 -*-


"""
Copyright (c) 2019 Valentin B.

A simple music bot written in discord.py using youtube-dl.

Though it's a simple example, music bots are complex and require much time and knowledge until they work perfectly.
Use this as an example or a base for your own bot and extend it as you want. If there are any bugs, please let me know.

Requirements:

Python 3.5+
You also need FFmpeg in your PATH environment variable or the FFmpeg.exe binary in your bot's directory on Windows.

"""

#Requiere estos paquetes ahora
#python -m pip install -U discord.py pynacl youtube-dl requests beautifulsoup4
#FFmpeg en el path

'''
davod0401:
Comandos traducidos y arreglados (algunos no funcionaban) se añadieron aliases para los comandos comunes eg. play > p
Comando de ayuda.
Rutina para buscar enlaces de spotify en youtube.


To do: *Usar libreria spotipy para parsear playlists. Esto puede ser problematico si se añaden todas las canciones a la vez
y no se encuentra alguna en youtube... deberia buscar una por una? en grupos?...
*Port Youtube-dl to yt-dlp??? No hace falta por ahora...
'''
import asyncio
import functools
import itertools
import math
import random
import requests
from bs4 import BeautifulSoup

import discord
import youtube_dl
from async_timeout import timeout
from discord.ext import commands

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ''

# Variables de configuracion
voteskip = False #Requerir votacion para saltar canciones
idle_timeout = 180 #Tiempo inactivo para autodesconectar
default_volume = 0.5 #Volumen por defecto


def spotify_parse(search:str):
    '''Funcion que comprueba si la busqueda realizada es un enlace de spotify,
       si lo es extrae el titulo de la cancion y lo retorna,
       de lo contrario retorna la misma busqueda'''
       
    if search.startswith('https://open.spotify.com/track'):
        URL = search
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        #print(soup.find('title'))
        title = soup.title.get_text().split('|')
        title_s = title[0]
        return title_s
    elif search.startswith('https://open.spotify.com/playlist'):
        raise ValueError("No se aceptan playlists de spotify(por ahora)")
    else:
        return search

class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data
        #Pa que todo esto?
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError('No se pudo encontrar `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('No se pudo encontrar `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('No se pudo encontrar `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('No se pudo encontrar `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} dias'.format(days))
        if hours > 0:
            duration.append('{} horas'.format(hours))
        if minutes > 0:
            duration.append('{} minutos'.format(minutes))
        if seconds > 0:
            duration.append('{} segundos'.format(seconds))

        return ', '.join(duration)


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (discord.Embed(title='Reproduciendo ahora',
                               description='```css\n{0.source.title}\n```'.format(self),
                               color=discord.Color.blurple())
                 .add_field(name='Duración', value=self.source.duration)
                 .add_field(name='Solicitado por', value=self.requester.mention)
                 .add_field(name='Autor', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
                 .add_field(name='URL', value='[Click]({0.source.url})'.format(self))
                 .set_thumbnail(url=self.source.thumbnail))

        return embed


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = default_volume
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            if not self.loop:
                # Try to get the next song within 3 minutes.
                # If no song will be added to the queue in time,
                # the player will disconnect due to performance
                # reasons.
                try:
                    async with timeout(idle_timeout): #Tiempo ajustable 
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)
            await self.current.source.channel.send(embed=self.current.create_embed())

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send('Ocurrio un error: {}'.format(str(error)))

    @commands.command(name='join', invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        """Joins a voice channel."""

        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='summon')
    @commands.has_permissions(manage_guild=True)
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        """Summons the bot to a voice channel.

        If no channel was specified, it joins your channel.
        """

        if not channel and not ctx.author.voice:
            raise VoiceError('No estas conectado en ningun canal o no se especifico un canal para conectarse')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect', 'dc'])
    @commands.has_permissions(manage_guild=True)
    async def _leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""

        if not ctx.voice_state.voice:
            return await ctx.send('No estas conectado a ningun canal')

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='volumen', aliases=['vol'])
    async def _volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('No hay nada en reproducción')

        if 0 > volume > 100:
            return await ctx.send('El volumen debe ser entre 0 y 100')

        ctx.voice_state.volume = volume / 100
        await ctx.send('Volumen ajustado a {}%'.format(volume))

    @commands.command(name='now', aliases=['current', 'playing'])
    async def _now(self, ctx: commands.Context):
        """Displays the currently playing song."""

        await ctx.send(embed=ctx.voice_state.current.create_embed())

    @commands.command(name='pausa')
    @commands.has_permissions(manage_guild=True)
    async def _pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resumir')
    @commands.has_permissions(manage_guild=True)
    async def _resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""

        if not ctx.voice_state.voice.is_playing() and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop', aliases=['clear'])
    @commands.has_permissions(manage_guild=True)
    async def _stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""

        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip', aliases=['next', 's'])
    async def _skip(self, ctx: commands.Context):
        """Si voteskip = True: Vote to skip a song. The requester can automatically skip.
        3 skip votes are needed for the song to be skipped.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('No hay nada que saltar...')
        if voteskip:

            voter = ctx.message.author
            if voter == ctx.voice_state.current.requester:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()

            elif voter.id not in ctx.voice_state.skip_votes:
                ctx.voice_state.skip_votes.add(voter.id)
                total_votes = len(ctx.voice_state.skip_votes)

                if total_votes >= 3:
                    await ctx.message.add_reaction('⏭')
                    ctx.voice_state.skip()
                else:
                    await ctx.send('Skip vote added, currently at **{}/3**'.format(total_votes))

            else:
                await ctx.send('You have already voted to skip this song.')
        else:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

    @commands.command(name='lista', aliases=['l'])
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.

        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Lista vacia.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} canciones:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='Pagina {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='aleatorio', aliases=['random'])
    async def _shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Lista vacia')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='quitar', aliases=['r'])
    async def _remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Lista vacia')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='repetir', aliases=['bucle', 'loop'])
    async def _loop(self, ctx: commands.Context):
        """Loops the currently playing song.

        Invoke this command again to unloop the song.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Lista vacia')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        """Plays a song.

        If there are songs in the queue, this will be queued until the
        other songs finished playing.

        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        
        Extendido para procesar urls de spotify
        """

        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        async with ctx.typing():
            try:
                yt_query = spotify_parse(search)
            except ValueError as ee:
                await ctx.send('Ocurrio un error procesando la petición: {}'.format(str(ee)))
            try:
                source = await YTDLSource.create_source(ctx, yt_query, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('Ocurrio un error procesando la petición: {}'.format(str(e)))
            else:
                song = Song(source)

                await ctx.voice_state.songs.put(song)
                await ctx.send('Añadido {}'.format(str(source)))

    @commands.command(name='ayuda', aliases=['comandos'])
    async def _ayuda(self, ctx: commands.Context):
        """Muestra un embed de ayuda con todos los comandos del bot"""
        embedh = (discord.Embed(title='Comandos Janky',
                               description='Pagina de ayuda Janky bot',
                               color=discord.Color.blurple())
                 .add_field(name='play, p', value="Añadir canción a la lista. Acepta texto y links", inline=False)
                 .add_field(name='leave, disconnect, dc', value="Vacia la lista y desconecta el bot", inline=False)
                 .add_field(name='skip, next, s', value="Pasa a la siguiente canción", inline=False)
                 .add_field(name='aleatorio, random', value="Ordena la lista de forma aleatoria", inline=False)
                 .add_field(name='lista, l', value="Muestra la lista de reproducción", inline=False)
                 .add_field(name='stop, clear', value="Borra la lista de reproducción", inline=False)
                 .add_field(name='quitar, r', value="Elimina la canción de la lista con el indice indicado", inline=False)
                 .add_field(name='repetir, bucle, loop', value="Repite la canción actual hasta que se desactive", inline=False)
                 .add_field(name='volumen, vol', value="Ajusta el volumen de la siguiente canción", inline=False)
                 .add_field(name='pausa', value="Pausa la reproducción", inline=False)
                 .add_field(name='resumir', value="Reanuda la reproducción", inline=False)
                 .add_field(name='summon', value="Mueve el bot al canal escrito o al actual si no se especifica", inline=False)
        )
                 #.set_thumbnail(url=self.source.thumbnail))

        await ctx.send(embed=embedh)

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('No estas conectado a ningun canal de voz.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Ya estoy en este canal.')


bot = commands.Bot('-', description='A falta de groovy.')
bot.add_cog(Music(bot))


@bot.event
async def on_ready():
    print('Logged in as:\n{0.user.name}\n{0.user.id}'.format(bot))

bot.run('token')