from abc import ABC, abstractmethod


class AbstractDestination(ABC):
    @abstractmethod
    async def send(self, payload: dict) -> None: ...

    async def aclose(self) -> None:
        pass
