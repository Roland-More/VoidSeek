import argparse
import sys
import os

# Zaistíme, aby bol src priečinok v ceste pre importy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.game_server import GameServer

def main():
    parser = argparse.ArgumentParser(description="VoidSeek Dedicated Server")
    parser.add_argument("--name", type=str, default="VoidSeek Server", help="Názov servera")
    parser.add_argument("--tcp-port", type=int, default=7777, help="TCP port pre pripojenia")
    parser.add_argument("--udp-port", type=int, default=7778, help="UDP broadcast port")
    parser.add_argument("--max-players", type=int, default=4, help="Maximálny počet hráčov")
    parser.add_argument("--map-size", type=int, default=32, choices=[32,64, 96], help="Veľkosť mapy (64 alebo 96)")
    
    args = parser.parse_args()
    
    server = GameServer(
        name=args.name,
        tcp_port=args.tcp_port,
        udp_port=args.udp_port,
        max_players=args.max_players,
        map_size=args.map_size
    )
    
    server.run()

if __name__ == "__main__":
    main()
