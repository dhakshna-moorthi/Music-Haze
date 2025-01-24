from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from requests import get, post
from openai import OpenAI
import random
import base64
import json
import os

app = Flask(__name__)
app.secret_key = os.getenv("APP_KEY")

load_dotenv()

LLMFOUNDRY_TOKEN = os.getenv("LLMFOUNDRY_TOKEN")
BASE_URL = os.getenv("BASE_URL")

client = OpenAI(
    api_key=f"{LLMFOUNDRY_TOKEN}:music-haze",
    base_url=BASE_URL,
) 

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

song_list = []

letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
first_letter = random.choice(letters)
fixed_letter = first_letter

def get_token():
    auth_string=SPOTIFY_CLIENT_ID+":"+SPOTIFY_CLIENT_SECRET
    auth_bytes=auth_string.encode("utf-8")
    auth_base64=str(base64.b64encode(auth_bytes),"utf-8")
    url="https://accounts.spotify.com/api/token"
    headers={"Authorization":"Basic "+auth_base64,
             "content-type":"application/x-www-form-urlencoded"
            }
    data = {
        "grant_type": "client_credentials",
        "redirect_uri": "spotify.com"
    }
    result=post(url,headers=headers,data=data,verify=False)
    json_result=json.loads(result.content)
    token=json_result["access_token"]
    return token

def get_auth_header(token):
    return {"Authorization":"Bearer "+token}

def verify_song(song, artist):
    url = "https://api.spotify.com/v1/search"
    token = get_token()
    headers = get_auth_header(token)
    query = f"?q=track:{song} artist:{artist}&type=track&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers, verify=False)
    json_result = json.loads(result.content)
    
    if 'tracks' in json_result and json_result['tracks']['items']:
        return True
    return False

def chat_completion(prompt):
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="gpt-4o-mini",
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content

def validate_song(song, artist, current_letter):
    print(song, artist, current_letter)
    if song[0].lower() != current_letter.lower():
        return 'Given letter and first letter of song do not match'
    if song.lower() in song_list:
        return 'Song was already used in an previous round'
    
    result = verify_song(song,artist)

    if not result:
        return "The spotify database doesn't contain the given song"

    return 'correct'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['mode'] = request.form['mode']
        session['player1'] = request.form['player1']
        if session['mode'] == 'solo':
            return redirect(url_for('home', username=session['player1']))
        elif session['mode'] == '2player':
            session['player2'] = request.form['player2']
            return redirect(url_for('home', username=f"{session['player1']} and {session['player2']}"))
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    global first_letter  

    if session['mode'] == 'solo':
        session['greeting'] = session['player1']
    else:
        session['greeting'] = f"{session['player1']} and {session['player2']}"
    
    if 'history' not in session: session['history'] = []
    if 'player' not in session: session['player'] = session['player1']
    if 'player-num' not in session: session['player-num'] = ''
    if 'non-player' not in session: session['non-player'] = ''
    if 'score' not in session: session['score'] = 0
    if 'result' not in session: session['result'] = ''
    if 'winner' not in session: session['winner'] = ''
    
    if session['winner'] == '':

        if request.method == 'POST':

            if session['mode'] == '2player':
                if session['score']%2==0:
                    session['player'] = session['player1']
                    session['player-num'] = 'one'
                    session['non-player'] = session['player2']
                else:
                    session['player'] = session['player2']
                    session['player-num'] = 'two'
                    session['non-player'] = session['player1']
            
            song_artist = request.form['song']

            song = song_artist.split('-')[0].strip()
            artist = song_artist.split('-')[1].strip()

            message = validate_song(song, artist, first_letter)

            if message == 'correct':
                print(song )
                last_letter = song[-1]

                if session['mode'] == 'solo':
                    status = "Correct! Now it's Bot's turn"
                else:
                    status = f"Correct! Now it's {session['non-player']}'s turn. Enter a song starting with {last_letter.upper()}"

                session['history'].append({
                    'player': session['player'],
                    'playernum': session['player-num'],
                    'letter': first_letter.upper(),
                    'song': song,
                    'artist': artist,
                    'message': status
                })
                
                first_letter = last_letter.upper()
                song_list.append(song.lower())
                session['score'] = session['score'] + 1
                session.modified = True 

                if session['mode'] == 'solo':
                    if session['score']%2!=0:

                        song_list_str = ", ".join(song_list)

                        bot_prompt = f"""Return a song name that starts with the letter '{first_letter}'. 
                                    Your response should be in the following format ```song_name - artist_name``` without any delimiters such as quotes. 
                                    Your response must not be one of the following songs '{song_list_str}'. 
                                    Your response must end with an alphabet, not any special characters such as single quotes or numbers."""
                        
                        bot_song_artist = chat_completion(bot_prompt)

                        bot_song = bot_song_artist.split('-')[0].strip()
                        bot_artist = bot_song_artist.split('-')[1].strip()

                        bot_message = validate_song(bot_song, bot_artist, first_letter)

                        if bot_message == 'correct':

                            last_letter = bot_song[-1]
                        
                            status = f"Your turn, enter a song starting with '{last_letter.upper()}'"
                            
                            session['history'].append({
                                'player': 'Bot',
                                'letter': first_letter.upper(),
                                'song': bot_song,
                                'artist': bot_artist,
                                'message': status
                            })

                            first_letter = last_letter.upper()
                            song_list.append(bot_song.lower())
                            session['score'] = session['score'] + 1
                            session.modified = True 
                        
                        else:
                            session['history'].append({
                                'player': 'Bot',
                                'letter': first_letter.upper(),
                                'song': bot_song,
                                'artist': bot_artist,
                                'message': bot_message
                            })

                            session['result'] = f"You Won! Your Score is {str(int(session['score']/2))}"
                            session['winner'] = 'user'

            else:
                session['history'].append({
                    'player': session['player'],
                    'playernum': session['player-num'],
                    'letter': first_letter.upper(),
                    'song': song,
                    'artist': artist,
                    'message': message
                })

                if session['mode'] == 'solo':
                    session['result'] = f"Bot won. Your Score is {str(int(session['score']/2))}"
                    session['winner'] = 'bot'
                else:
                    session['result'] = f"{session['non-player']} won! Total number of rounds: {str(int(session['score']/2))}"
                    session['winner'] = 'user'

    return render_template('index.html', username=session['greeting'], player_one=session['player1'], first_letter=fixed_letter, history=session['history'], result=session['result'], winner=session['winner'])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
