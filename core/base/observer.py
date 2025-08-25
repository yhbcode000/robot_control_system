from abc import ABC, abstractmethod
from typing import Any, List, Callable


class Observable:
    def __init__(self):
        self._observers: List[Observer] = []
        self._callbacks: List[Callable] = []
    
    def attach(self, observer: 'Observer'):
        if observer not in self._observers:
            self._observers.append(observer)
    
    def detach(self, observer: 'Observer'):
        if observer in self._observers:
            self._observers.remove(observer)
    
    def attach_callback(self, callback: Callable):
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def detach_callback(self, callback: Callable):
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def notify(self, event: str, data: Any = None):
        for observer in self._observers:
            try:
                observer.update(self, event, data)
            except Exception as e:
                print(f"Observer notification failed: {e}")
        
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception as e:
                print(f"Callback notification failed: {e}")


class Observer(ABC):
    @abstractmethod
    def update(self, observable: Observable, event: str, data: Any = None):
        pass