# models/base_model.py
from abc import ABC, abstractmethod

class BaseModel(ABC):
    @abstractmethod
    def generar_respuesta(self, mensaje_usuario: str, prompt_sistema: str) -> str:
        pass


