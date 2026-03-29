import asyncio
import os
import logging

GATEWAY_ADDR = "0.0.0.0"
GATEWAY_PORT = 9999

BACKEND_ADDR = os.environ.get("BACKEND_ADDR", "backend")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 8888))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatagramReceiver(asyncio.DatagramProtocol):
    """
    Обработчик UDP-датаграмм.

    Принимает сырые UDP-пакеты, добавляет разделитель '\n' и помещает в очередь.
    При переполнении очереди пакет отбрасывается с предупреждением.
    """

    def __init__(self, dispatch_queue: asyncio.Queue) -> None:
        self.dispatch_queue = dispatch_queue

    def datagram_received(self, data: bytes, addr: tuple) -> None:

        framed_data = data + b"\n"
        try:
            self.dispatch_queue.put_nowait(framed_data)
        except asyncio.QueueFull:
            logger.warning("Queue overflow from %s. Packet dropped.", addr)


async def reliable_forwarder(
    queue: asyncio.Queue, destination_host: str, destination_port: int
) -> None:
    """
    читает пакеты из очереди и отправляет их по TCP с рекконектом в 3с
    """
    while True:
        try:
            logger.info(
                "Initializing transmission context %s:%d",
                destination_host,
                destination_port,
            )
            reader, writer = await asyncio.open_connection(
                destination_host, destination_port
            )
            logger.info("Tunnel bound actively.")

            while True:
                packet = await queue.get()
                writer.write(packet)
                await writer.drain()
                queue.task_done()

        except (ConnectionError, BrokenPipeError, TimeoutError) as network_error:
            logger.error(
                "Pipe integrity compromise: %s. Suspending link configuration...",
                network_error,
            )
            await asyncio.sleep(3)

        except Exception as software_exception:
            logger.critical("Critical subsystem bypass: %s", software_exception)
            await asyncio.sleep(3)


async def main() -> None:
    """
    Точка входа: инициализирует очередь, запускает форвардер и UDP-сервер.
    потециальные проблемы:
    - Задача reliable_forwarder не отменяется при shutdown
    - asyncio.Future() без отмены = вечное ожидание
    - transport.close() без await может привести к утечке ресурсов
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=16384)
    asyncio.create_task(reliable_forwarder(queue, BACKEND_ADDR, BACKEND_PORT))

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DatagramReceiver(queue), local_addr=(GATEWAY_ADDR, GATEWAY_PORT)
    )

    logger.info("Awaiting telemetry interfaces on port UDP %d", GATEWAY_PORT)
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        transport.close()
        logger.info("Services suspended gracefully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Программа остановлена пользователем.")
