import asyncio
import os

GATEWAY_ADDR = "0.0.0.0"
GATEWAY_PORT = 9999

BACKEND_ADDR = os.environ.get("BACKEND_ADDR", "backend")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 8888))

stop_event = asyncio.Event()


class GatewayProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print("[!!!] Шлюз запущен: Слушаю UDP 9999 -> Пересылаю на TCP 8888\n")

    def datagram_received(self, data, addr):
        print(f"[UDP] Получил пакет от {addr[0]}:{addr[1]}")
        message = data.decode('utf-8').strip()
        if message == "EXIT":
            print("\n[!] Получен сигнал завершения. Остановка шлюза...")
            stop_event.set()    
        else:
            asyncio.create_task(forward_tcp_server(data))

async def forward_tcp_server(data):
    try: 
        reader, writer = await asyncio.open_connection(
            BACKEND_ADDR,
            BACKEND_PORT
        )
        
        writer.write(data)
        await writer.drain()

        server_backend = writer.get_extra_info('peername')

        print(f"[TCP] Переслал пакет на сервер: {server_backend[0]}:{server_backend[1]}\n")

        writer.close()
        await writer.wait_closed()

    except Exception as e:
        print(f"\n[!] Ошибка TCP-пересылки - {e}")



async def main():
    loop = asyncio.get_running_loop()
 
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: GatewayProtocol(),
        local_addr=(
            GATEWAY_ADDR,
            GATEWAY_PORT
        )
    )

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        print("[!] Получен сигнал завершения. Остановка шлюза внутри...")
    finally:
        transport.close()
        print("[!] Сетевой шлюз закрыт.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[!!!] Программа полностью остановлена пользователем.")
