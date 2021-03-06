# Get MLB scores for games played on given day and display on LED matrix.
# Uses MLB-SStatsAPI by GitHub user toddrob99  https://github.com/toddrob99/MLB-StatsAPI
# James S. Lucas - 20210522

import RPi.GPIO as GPIO
import datetime
from smbus import SMBus
import atexit
from time import sleep
#from random import randint
import argparse
from requests.exceptions import ReadTimeout
from urllib3.exceptions import MaxRetryError, NewConnectionError, ConnectionError
import statsapi

pwr_pin = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(pwr_pin, GPIO.OUT)
GPIO.output(pwr_pin, GPIO.LOW)

# Stepper Arduino I2C address
addr_stepper = 0x08

# LED Matrix Arduino I2C address
addr_led = 0x06

bus = SMBus(1)

num_i2c_errors = 0
last_i2c_error_time = datetime.datetime.now()


def get_arguments():
   parser = argparse.ArgumentParser(
   description='Display MLB game scores and win percentage for a given date.',
   prog='mlbometer',
   usage='%(prog)s [-d <date>], [-s <spoilers off>]',
   formatter_class=argparse.RawDescriptionHelpFormatter,
   )
   g=parser.add_argument_group(title='arguments',
         description='''    -y, --year   year to get data for.
   -d  --date  mm/dd/yyyy.
   -s  --spoiler  spoiler off (hard coded SF Giants).                                                       ''') 
   g.add_argument('-d', '--date',
                  type=str,
                  dest='date',
                  help=argparse.SUPPRESS)
   g.add_argument('-s', '--spoiler',
                  action='store_true',
                  dest='spoiler',
                  help=argparse.SUPPRESS)

   args = parser.parse_args()
   return(args)


def exit_function():
    '''Function disconnects stream and resets motor positions to zero. 
    Called by exception handler'''
    print(" ")
    print("End by atexit")
    led_write_time_1 = datetime.datetime.now()
    led_write_time_2 = datetime.datetime.now()
    global pwr_pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pwr_pin, GPIO.OUT)
    write_time = datetime.datetime.now()
    sleep(1)
    zero_gauges(write_time)
    sleep(.5)
    led_write_time_1 = write_matrix(" ", "1", led_write_time_1)
    sleep(.2)
    led_write_time_2 = write_matrix(" ", "0", led_write_time_2)
    sleep(3)
    GPIO.output(pwr_pin, GPIO.LOW)
    sleep(.5)
    GPIO.cleanup()
    sleep(.5)
   #system("stty echo")
    exit()


atexit.register(exit_function)


def i2c_error_tracker():
    global last_i2c_error_time
    global num_i2c_errors
    global pwr_pin
    duration_since_last_error = datetime.datetime.now() - last_i2c_error_time
    last_i2c_error_time = datetime.datetime.now()
    if duration_since_last_error.total_seconds() <= 2:
        num_i2c_errors += 1
        print(str(num_i2c_errors))
    elif duration_since_last_error.total_seconds() > 2:
        num_i2c_errors = 0
    if num_i2c_errors > 2:
        num_i2c_errors = 0
        #GPIO.setmode(GPIO.BCM)
        #GPIO.setup(pwr_pin, GPIO.OUT)
        GPIO.output(pwr_pin, GPIO.LOW)
        sleep(2)
        GPIO.output(pwr_pin, GPIO.HIGH)
        sleep(4)
    return


def StringToBytes(src): 
    '''Function converts a string to an array of bytes'''
    converted = [] 
    for b in src: 
        converted.append(ord(b)) 
        #print(converted)
    return converted


def writeData(motor_num, value):
    '''Function writes the command string to the  Stepper Arduino'''
    try:
        byteValue = StringToBytes(value)
        #print(byteValue)
        bus.write_i2c_block_data(addr_stepper, motor_num, byteValue)
        #sleep(.02)
    except OSError as e:
        print("Stepper I2C Communication Error")
        print(" ")
        i2c_error_tracker()
        pass


def write_matrix(msg, display_num, led_write_time):
    '''Function writes the command string to the LED Arduino'''
    try:
        byteValue = StringToBytes(msg)
        num_chars = len(byteValue)
        num_whole_blocks, chars_in_last_block = divmod(num_chars, 30)
        if chars_in_last_block > 0:
            num_blocks = num_whole_blocks + 1
        else:
             num_blocks = num_whole_blocks
        for b in range(num_blocks):
            if b <= (num_blocks - 2):
                #if more than one block print the first block
                #rem_chars = num_chars - ((b + 1) * 30)
                strt_range = b * 30
                end_range = strt_range + 30
                msg = byteValue[strt_range : end_range]
                bus.write_i2c_block_data(addr_led, 0x1, msg)
                sleep(.0005)
            else:
                #print the first block if only one block or the last block if more than one
                #rem_chars = 0
                strt_range = b * 30
                end_range = num_chars
                msg = byteValue[strt_range : end_range]
                msg.append(ord(display_num))
                #print(str(strt_range) + "/" + str(end_range) + "/" + str(len(msg)))
                #print(msg)
                bus.write_i2c_block_data(addr_led, 0x3, msg)
                led_write_time = datetime.datetime.now()
                sleep(.0005)
        return led_write_time
    except OSError as e:
        #led_write_time = datetime.datetime.now()
        print("LED Matrix I2C Communication Error")
        print(" ")
        i2c_error_tracker()
        return led_write_time
        pass


def move_stepper(indicator_pos_1, indicator_pos_2, write_time):
    '''Function prepares the command string and sends to WriteData()'''
    # Format is XYYYY where X is motor number and YYYY is 1-4 digit indicator postion
    elapsed_time = datetime.datetime.now() - write_time
    if elapsed_time.total_seconds() > .2:
        #command = indicator_pos_1
        motor_num = 0x01 
        position = indicator_pos_1
        writeData(motor_num, position)
        #print("B: " + str(indicator_pos_2))
        sleep(.00005)
        motor_num = 0x02
        position = indicator_pos_2
        writeData(motor_num, position)
        #print("T: " + str(indicator_pos_2))
        write_time = datetime.datetime.now()
    return write_time


def zero_gauges(write_time):
    indicator_pos_1 = 0
    indicator_pos_2 = 0
    write_time = move_stepper(str(indicator_pos_1), str(indicator_pos_2), write_time)



def get_games(spoiler, start_date, end_date):
    try:
        sched = statsapi.schedule(start_date, end_date)
        print(sched)
    except ReadTimeout:
        print("ReadTimeout Error")
        sleep(20)
        pass
    except NewConnectionError:
        print("NewConnection Error")
        sleep(20)
        pass
    except MaxRetryError:
        print("MaxRetry Error")
        sleep(20)
        pass
    except ConnectionError:
        print("Connection Error")
        sleep(20)
        pass
    games_list = []
    if sched:
        for game in sched:
            #print(game['game_id'], game['summary'])
            status = game['status']
            if 'Progress' not in status and 'Final' not in status:
                continue
            game_id = game['game_id']
            home_id = game['home_id']
            away_id = game['away_id']
            if spoiler:
                if home_id == 137 or away_id == 137:
                    continue
            home_name = game['home_name']
            away_name = game['away_name']
            home_score = game['home_score']
            away_score = game['away_score']
            if 'Final' not in status:
                home_str = f"{home_name} ({home_score})"
                away_str = f"{away_name} ({away_score})"
            else:
                if home_score > away_score:
                    home_str = f"{home_name} ({home_score}-{away_score}) W"
                    away_str = f"{away_name} ({away_score}-{home_score}) L"
                else:
                    home_str = f"{home_name} ({home_score}-{away_score}) L"
                    away_str = f"{away_name} ({away_score}-{home_score}) W"
            home_team = statsapi.get('team', {'teamId':home_id})
            away_team = statsapi.get('team', {'teamId':away_id})
            home_league = home_team['teams'][0]['league']['id']
            away_league = away_team['teams'][0]['league']['id']
            home_div = home_team['teams'][0]['division']['id']
            away_div = away_team['teams'][0]['division']['id']
            try:
                home_standings = statsapi.standings_data(leagueId=home_league, division="all", include_wildcard=True, season= datetime.datetime.now().year, standingsTypes=None, date=None)
                sleep(1)
                away_standings = statsapi.standings_data(leagueId=away_league, division="all", include_wildcard=True, season= datetime.datetime.now().year, standingsTypes=None, date=None)
            except ReadTimeout:
                print("ReadTimeout Error")
                sleep(20)
                pass
            except NewConnectionError:
                print("MewConnection Error")
                sleep(20)
                pass
            except MaxRetryError:
                print("MaxRetry Error")
                sleep(20)
                pass
            except ConnectionError:
                print(ConnectionError)
                sleep(20)
                pass

            #pprint.pprint(home_standings, width=1)
            #print(home_id, home_league, home_div)
            home_teams = home_standings[home_div]['teams']
            home_team_dict = next(item for item in home_teams if item["team_id"] == int(home_id))
            home_team_wins = home_team_dict['w']
            home_team_losses = home_team_dict['l']
            home_team_percentage = home_team_wins / (home_team_wins + home_team_losses) * 100
            away_teams = away_standings[away_div]['teams']
            away_team_dict = next(item for item in away_teams if item["team_id"] == int(away_id))
            away_team_wins = away_team_dict['w']
            away_team_losses = away_team_dict['l']
            away_team_percentage = away_team_wins / (away_team_wins + away_team_losses) * 100

            game_list = [
                away_str, away_team_percentage,
                home_str, home_team_percentage
                ]
            print(game_list)
            games_list.append(game_list)
            #print("Home wins: ", home_team_wins, "Away wins: ", away_team_wins)
    return games_list


# Main
try:
    args = get_arguments()

    led_write_time_1 = datetime.datetime.now()
    led_write_time_2 = datetime.datetime.now()
    write_time = datetime.datetime.now()
    GPIO.output(pwr_pin, GPIO.HIGH)
    sleep(4)
    write_time = move_stepper("0", "0", write_time)
    sleep(1)
    while True:
        ET = 0
        games_list = []
        while not games_list:
            games_list = get_games(args.spoiler, args.date, args.date)
            sleep(15)
        #sleep(1)
        #led_write_time_2 = write_matrix(track_string, "0", led_write_time_2)
        #sleep(0.5)
            #write_time = move_stepper(str(int(popularity * 21)), str(int(percent_complete * 21)), write_time)
        while ET <= 180:
            sleep(1)
            zeroed = 0
            for game in games_list:
                print(game[0], ' at ', game[2])
                led_write_time_1 = write_matrix(game[0], "1", led_write_time_1)
                sleep(.2)
                led_write_time_2 = write_matrix(game[2], "0", led_write_time_2)
                sleep(.2)
                write_time = move_stepper(str(int(game[1] * 21 + 10)), str(int(game[3] * 21)), write_time)
                sleep(12)
                if ET >= 90 and zeroed == 0:
                    zero_gauges(write_time)
                    sleep(.05)
                    zeroed = 1
                #write_time = move_stepper(str(int(popularity * 21)), str(int(percent_complete * 21)), write_time)
                ET += 12.5
except KeyboardInterrupt:
    print(" ")
    print("End by Ctrl-C")
    #sleep(3)
    #GPIO.output(pwr_pin, GPIO.LOW)
    #sleep(.5)
    #GPIO.cleanup()
    #sleep(1)
    #exit()