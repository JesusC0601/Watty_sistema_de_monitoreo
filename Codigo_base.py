"""
=====================================================================
 SISTEMA DE MONITOREO Y CONTROL ENERGÉTICO RESIDENCIAL
 Prototipo lógico en Python puro
 Arquitectura: ESP32 (IoT) -> Backend Python -> App Móvil con IA
=====================================================================

Estructuras de datos implementadas:
 1. Árbol jerárquico (Tree)      -> Vivienda / Caja ESP32 / Breakers
 2. Cola FIFO (Queue)            -> Flujo de lecturas de sensores
 3. Tabla Hash (dict)            -> Estado, límites y alertas O(1)
 4. Motor de IA simulado         -> Detección de sobrecargas

Autor: Prototipo generado como base de desarrollo (POO, modular)
=====================================================================
"""

from __future__ import annotations

import random
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Deque, Dict, List, Optional


# =====================================================================
# 1. MODELOS DE DATOS BÁSICOS
# =====================================================================

class EstadoBreaker(Enum):
    """Estados posibles de un circuito/breaker."""
    ENCENDIDO = "ENCENDIDO"
    APAGADO = "APAGADO"


class PrioridadAlerta(Enum):
    """Niveles de prioridad para las alertas generadas por la IA."""
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


@dataclass
class LecturaSensor:
    """
    Representa una lectura instantánea enviada por la ESP32
    para un breaker específico (voltaje, corriente, potencia).
    """
    breaker_id: str
    voltaje: float          # Volts (V)
    corriente: float        # Amperios (A)
    potencia: float         # Watts (W)
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return (f"[{self.timestamp.strftime('%H:%M:%S')}] "
                f"{self.breaker_id} -> {self.voltaje:.1f}V, "
                f"{self.corriente:.2f}A, {self.potencia:.1f}W")


@dataclass
class Alerta:
    """Alerta generada por el motor de IA cuando detecta una anomalía."""
    id_alerta: str
    breaker_id: str
    mensaje: str
    prioridad: PrioridadAlerta
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return (f"[{self.prioridad.value}] ({self.timestamp.strftime('%H:%M:%S')}) "
                f"{self.breaker_id}: {self.mensaje}")


# =====================================================================
# 2. ÁRBOL JERÁRQUICO (TREE)
#    Vivienda (Raíz) -> Caja ESP32 (Nodo Hijo) -> Breakers (Hojas)
# =====================================================================

class NodoBreaker:
    """
    Nodo HOJA del árbol. Representa un circuito individual controlado
    por un breaker físico conectado a la caja ESP32.
    """

    def __init__(self, breaker_id: str, nombre: str, limite_amperaje: float):
        self.breaker_id = breaker_id
        self.nombre = nombre
        self.limite_amperaje = limite_amperaje
        self.estado = EstadoBreaker.ENCENDIDO
        self.potencia_actual: float = 0.0  # Watts, actualizado por la IA/lecturas

    def encender(self) -> None:
        self.estado = EstadoBreaker.ENCENDIDO

    def apagar(self) -> None:
        """Aísla el circuito (corte remoto por seguridad o por el usuario)."""
        self.estado = EstadoBreaker.APAGADO
        self.potencia_actual = 0.0

    def consumo_kw(self) -> float:
        """Consumo del breaker en kW. Si está apagado, no consume."""
        if self.estado == EstadoBreaker.APAGADO:
            return 0.0
        return self.potencia_actual / 1000.0

    def __repr__(self) -> str:
        return (f"  └─ Breaker [{self.breaker_id}] {self.nombre} | "
                f"{self.estado.value} | Límite: {self.limite_amperaje}A | "
                f"Consumo: {self.consumo_kw():.3f} kW")


class NodoCajaESP32:
    """
    Nodo INTERMEDIO del árbol. Representa una tarjeta ESP32 física
    que agrupa varios breakers/circuitos monitoreados.
    """

    def __init__(self, caja_id: str, nombre: str):
        self.caja_id = caja_id
        self.nombre = nombre
        self.breakers: Dict[str, NodoBreaker] = {}

    def agregar_breaker(self, breaker: NodoBreaker) -> None:
        self.breakers[breaker.breaker_id] = breaker

    def consumo_total_kw(self) -> float:
        """Suma recursiva del consumo de todos los breakers hijos."""
        return sum(b.consumo_kw() for b in self.breakers.values())

    def buscar_breaker(self, breaker_id: str) -> Optional[NodoBreaker]:
        return self.breakers.get(breaker_id)

    def __repr__(self) -> str:
        lineas = [f" ├─ Caja ESP32 [{self.caja_id}] {self.nombre} "
                  f"| Subtotal: {self.consumo_total_kw():.3f} kW"]
        for b in self.breakers.values():
            lineas.append(f" {b}")
        return "\n".join(lineas)


class NodoVivienda:
    """
    Nodo RAÍZ del árbol. Representa la vivienda completa, que puede
    contener una o varias cajas ESP32 (por ejemplo, tablero principal
    y sub-tableros).
    """

    def __init__(self, nombre: str):
        self.nombre = nombre
        self.cajas: Dict[str, NodoCajaESP32] = {}

    def agregar_caja(self, caja: NodoCajaESP32) -> None:
        self.cajas[caja.caja_id] = caja

    def calcular_consumo_total(self) -> float:
        """
        Método recursivo que recorre el árbol completo:
        Vivienda -> Cajas -> Breakers, acumulando el consumo en kW.
        """
        total = 0.0
        for caja in self.cajas.values():
            total += caja.consumo_total_kw()  # recursión implícita por nivel
        return total

    def buscar_breaker_global(self, breaker_id: str) -> Optional[NodoBreaker]:
        """Busca un breaker en cualquier caja de la vivienda."""
        for caja in self.cajas.values():
            breaker = caja.buscar_breaker(breaker_id)
            if breaker:
                return breaker
        return None

    def cambiar_estado_breaker(self, breaker_id: str, encender: bool) -> bool:
        """Aísla o reactiva un breaker específico en cualquier punto del árbol."""
        breaker = self.buscar_breaker_global(breaker_id)
        if breaker is None:
            return False
        breaker.encender() if encender else breaker.apagar()
        return True

    def imprimir_jerarquia(self) -> str:
        lineas = [f"🏠 Vivienda: {self.nombre} "
                  f"| Consumo total: {self.calcular_consumo_total():.3f} kW"]
        for caja in self.cajas.values():
            lineas.append(str(caja))
        return "\n".join(lineas)


# =====================================================================
# 3. TABLA HASH (Diccionario) - Estado, límites e historial de alertas
# =====================================================================

class RegistroCentral:
    """
    Estructura basada en diccionarios (Hash Map) que permite
    acceso O(1) a:
      - Estado y límite de amperaje de cada breaker.
      - Historial de alertas por breaker.
    """

    def __init__(self):
        # breaker_id -> {"estado":..., "limite_amperaje":..., "nombre":...}
        self.info_breakers: Dict[str, Dict] = {}
        # breaker_id -> lista de Alertas
        self.alertas_por_breaker: Dict[str, List[Alerta]] = {}
        # Todas las alertas activas, en orden de llegada
        self.alertas_activas: List[Alerta] = []

    def registrar_breaker(self, breaker: NodoBreaker) -> None:
        self.info_breakers[breaker.breaker_id] = {
            "nombre": breaker.nombre,
            "estado": breaker.estado.value,
            "limite_amperaje": breaker.limite_amperaje,
        }
        self.alertas_por_breaker.setdefault(breaker.breaker_id, [])

    def actualizar_estado(self, breaker_id: str, estado: EstadoBreaker) -> None:
        if breaker_id in self.info_breakers:
            self.info_breakers[breaker_id]["estado"] = estado.value

    def consultar_info(self, breaker_id: str) -> Optional[Dict]:
        """Consulta O(1) del estado/límite de un breaker."""
        return self.info_breakers.get(breaker_id)

    def agregar_alerta(self, alerta: Alerta) -> None:
        self.alertas_activas.append(alerta)
        self.alertas_por_breaker.setdefault(alerta.breaker_id, []).append(alerta)

    def historial_de(self, breaker_id: str) -> List[Alerta]:
        return self.alertas_por_breaker.get(breaker_id, [])


# =====================================================================
# 4. COLA FIFO (Queue) - Buffer de lecturas de sensores ESP32
# =====================================================================

class ColaLecturas:
    """
    Cola FIFO estricta para almacenar las lecturas que llegan desde
    la ESP32 antes de ser procesadas por el motor de IA.
    Se implementa sobre collections.deque para O(1) en enqueue/dequeue.
    """

    def __init__(self):
        self._cola: Deque[LecturaSensor] = deque()

    def encolar(self, lectura: LecturaSensor) -> None:
        self._cola.append(lectura)

    def desencolar(self) -> Optional[LecturaSensor]:
        if self._cola:
            return self._cola.popleft()
        return None

    def esta_vacia(self) -> bool:
        return len(self._cola) == 0

    def tamano(self) -> int:
        return len(self._cola)


# =====================================================================
# 5. MOTOR DE IA / ALERTAS (simulado)
# =====================================================================

class MotorIA:
    """
    Motor simulado de Inteligencia Artificial. Procesa la Cola de
    lecturas en orden cronológico (FIFO), actualiza el árbol de
    consumo y evalúa condiciones de sobrecarga contra los límites
    definidos en la Tabla Hash (RegistroCentral).
    """

    # Margen de tolerancia antes de considerar "sobreconsumo" (80% del límite)
    UMBRAL_ADVERTENCIA = 0.8

    def __init__(self, vivienda: NodoVivienda, registro: RegistroCentral):
        self.vivienda = vivienda
        self.registro = registro

    def procesar_cola(self, cola: ColaLecturas) -> List[Alerta]:
        """
        Extrae todas las lecturas pendientes de la cola, en estricto
        orden FIFO, actualiza el consumo del breaker correspondiente
        en el árbol y evalúa si hay sobrecarga.
        """
        nuevas_alertas: List[Alerta] = []

        while not cola.esta_vacia():
            lectura = cola.desencolar()
            if lectura is None:
                continue

            breaker = self.vivienda.buscar_breaker_global(lectura.breaker_id)
            if breaker is None or breaker.estado == EstadoBreaker.APAGADO:
                # Breaker inexistente o aislado: se ignora la lectura
                continue

            # Actualiza el consumo real en el nodo del árbol
            breaker.potencia_actual = lectura.potencia

            alerta = self._evaluar_sobrecarga(breaker, lectura)
            if alerta:
                self.registro.agregar_alerta(alerta)
                nuevas_alertas.append(alerta)

        return nuevas_alertas

    def _evaluar_sobrecarga(self, breaker: NodoBreaker,
                             lectura: LecturaSensor) -> Optional[Alerta]:
        """
        Lógica de la 'IA': compara la corriente medida contra el
        límite de amperaje del circuito (obtenido de la Tabla Hash).
        """
        info = self.registro.consultar_info(breaker.breaker_id)
        if info is None:
            return None

        limite = info["limite_amperaje"]

        if lectura.corriente > limite:
            # Sobrecarga real: prioridad ALTA
            mensaje = (f"Sobrecarga detectada: {lectura.corriente:.2f}A "
                       f"supera el límite de {limite:.2f}A.")
            return Alerta(
                id_alerta=str(uuid.uuid4())[:8],
                breaker_id=breaker.breaker_id,
                mensaje=mensaje,
                prioridad=PrioridadAlerta.ALTA,
            )
        elif lectura.corriente > limite * self.UMBRAL_ADVERTENCIA:
            # Acercándose al límite: prioridad MEDIA (recomendación preventiva)
            mensaje = (f"Consumo elevado: {lectura.corriente:.2f}A "
                       f"({(lectura.corriente/limite)*100:.0f}% del límite).")
            return Alerta(
                id_alerta=str(uuid.uuid4())[:8],
                breaker_id=breaker.breaker_id,
                mensaje=mensaje,
                prioridad=PrioridadAlerta.MEDIA,
            )
        return None


# =====================================================================
# 6. SIMULADOR DE ESP32 (genera lecturas falsas para pruebas)
# =====================================================================

class SimuladorESP32:
    """
    Simula el envío de un lote de lecturas desde la tarjeta ESP32
    hacia el backend, encolándolas en estricto orden cronológico.
    """

    def __init__(self, vivienda: NodoVivienda):
        self.vivienda = vivienda

    def generar_lote(self, cola: ColaLecturas, cantidad: int = 5) -> None:
        breakers_ids = [
            b.breaker_id
            for caja in self.vivienda.cajas.values()
            for b in caja.breakers.values()
        ]
        if not breakers_ids:
            print("No hay breakers registrados en la vivienda.")
            return

        for _ in range(cantidad):
            breaker_id = random.choice(breakers_ids)
            breaker = self.vivienda.buscar_breaker_global(breaker_id)

            # Simula lecturas normales, y ocasionalmente un pico de sobrecarga
            base_amp = random.uniform(1.0, breaker.limite_amperaje * 0.7)
            if random.random() < 0.25:  # 25% de probabilidad de anomalía
                base_amp = breaker.limite_amperaje * random.uniform(0.85, 1.3)

            voltaje = round(random.uniform(115, 125), 1)
            corriente = round(base_amp, 2)
            potencia = round(voltaje * corriente, 1)

            lectura = LecturaSensor(
                breaker_id=breaker_id,
                voltaje=voltaje,
                corriente=corriente,
                potencia=potencia,
            )
            cola.encolar(lectura)
            time.sleep(0.02)  # pequeña pausa para simular orden temporal real


# =====================================================================
# 7. SISTEMA PRINCIPAL (orquesta todos los componentes)
# =====================================================================

class SistemaEnergetico:
    """Clase fachada que integra Árbol, Cola, Tabla Hash y Motor de IA."""

    def __init__(self, nombre_vivienda: str):
        self.vivienda = NodoVivienda(nombre_vivienda)
        self.registro = RegistroCentral()
        self.cola_lecturas = ColaLecturas()
        self.motor_ia = MotorIA(self.vivienda, self.registro)
        self.simulador = SimuladorESP32(self.vivienda)

    def agregar_caja(self, caja_id: str, nombre: str) -> NodoCajaESP32:
        caja = NodoCajaESP32(caja_id, nombre)
        self.vivienda.agregar_caja(caja)
        return caja

    def agregar_breaker(self, caja: NodoCajaESP32, breaker_id: str,
                         nombre: str, limite_amperaje: float) -> None:
        breaker = NodoBreaker(breaker_id, nombre, limite_amperaje)
        caja.agregar_breaker(breaker)
        self.registro.registrar_breaker(breaker)

    def alternar_breaker(self, breaker_id: str, encender: bool) -> bool:
        ok = self.vivienda.cambiar_estado_breaker(breaker_id, encender)
        if ok:
            estado = EstadoBreaker.ENCENDIDO if encender else EstadoBreaker.APAGADO
            self.registro.actualizar_estado(breaker_id, estado)
        return ok

    def simular_lote_y_evaluar(self, cantidad: int = 5) -> List[Alerta]:
        self.simulador.generar_lote(self.cola_lecturas, cantidad)
        return self.motor_ia.procesar_cola(self.cola_lecturas)


# =====================================================================
# 8. DATOS DE EJEMPLO (configuración inicial de la vivienda)
# =====================================================================

def construir_sistema_demo() -> SistemaEnergetico:
    """Crea una vivienda de ejemplo con una caja ESP32 y varios breakers."""
    sistema = SistemaEnergetico("Residencia Principal")

    caja_principal = sistema.agregar_caja("ESP32-01", "Tablero Principal")

    sistema.agregar_breaker(caja_principal, "BRK-01", "Aire Acondicionado", limite_amperaje=15.0)
    sistema.agregar_breaker(caja_principal, "BRK-02", "Cocina / Nevera", limite_amperaje=20.0)
    sistema.agregar_breaker(caja_principal, "BRK-03", "Iluminación General", limite_amperaje=10.0)
    sistema.agregar_breaker(caja_principal, "BRK-04", "Tomacorrientes Sala", limite_amperaje=12.0)

    return sistema


# =====================================================================
# 9. INTERFAZ DE CONSOLA (Menú interactivo)
# =====================================================================

class InterfazConsola:
    """Menú de texto para interactuar con el SistemaEnergetico."""

    def __init__(self, sistema: SistemaEnergetico):
        self.sistema = sistema

    def mostrar_menu(self) -> None:
        print("\n" + "=" * 60)
        print(" SISTEMA DE MONITOREO Y CONTROL ENERGÉTICO RESIDENCIAL ")
        print("=" * 60)
        print("1. Ver jerarquía del hogar y consumo total (kW)")
        print("2. Encender / Apagar un breaker")
        print("3. Simular lote de lecturas ESP32 y ejecutar IA")
        print("4. Ver alertas / recomendaciones activas")
        print("5. Salir")
        print("-" * 60)

    def ejecutar(self) -> None:
        while True:
            self.mostrar_menu()
            opcion = input("Seleccione una opción (1-5): ").strip()

            if opcion == "1":
                self._ver_jerarquia()
            elif opcion == "2":
                self._alternar_breaker()
            elif opcion == "3":
                self._simular_lote()
            elif opcion == "4":
                self._ver_alertas()
            elif opcion == "5":
                print("Cerrando sistema. ¡Hasta luego!")
                break
            else:
                print("⚠️  Opción inválida. Intente nuevamente.")

    def _ver_jerarquia(self) -> None:
        print("\n" + self.sistema.vivienda.imprimir_jerarquia())

    def _alternar_breaker(self) -> None:
        breaker_id = input("Ingrese el ID del breaker (ej. BRK-01): ").strip().upper()
        info = self.sistema.registro.consultar_info(breaker_id)
        if info is None:
            print(f"❌ No se encontró el breaker '{breaker_id}'.")
            return

        print(f"Estado actual de {breaker_id} ({info['nombre']}): {info['estado']}")
        accion = input("¿Desea (E)ncender o (A)pagar? ").strip().upper()

        if accion == "E":
            self.sistema.alternar_breaker(breaker_id, encender=True)
            print(f"✅ {breaker_id} encendido.")
        elif accion == "A":
            self.sistema.alternar_breaker(breaker_id, encender=False)
            print(f"⛔ {breaker_id} apagado (aislado).")
        else:
            print("⚠️  Opción inválida.")

    def _simular_lote(self) -> None:
        try:
            cantidad = int(input("¿Cuántas lecturas desea simular? (ej. 5): ").strip())
        except ValueError:
            cantidad = 5
            print("Valor no válido, usando 5 por defecto.")

        print(f"\n📡 Recibiendo {cantidad} lecturas desde la ESP32...")
        alertas = self.sistema.simular_lote_y_evaluar(cantidad)

        if alertas:
            print(f"\n🚨 La IA generó {len(alertas)} alerta(s) nueva(s):")
            for alerta in alertas:
                print(f"   {alerta}")
        else:
            print("\n✅ Lecturas procesadas. No se detectaron anomalías.")

    def _ver_alertas(self) -> None:
        alertas = self.sistema.registro.alertas_activas
        if not alertas:
            print("\n✅ No hay alertas activas en este momento.")
            return

        print(f"\n📋 Alertas activas ({len(alertas)}):")
        for alerta in sorted(alertas, key=lambda a: a.prioridad.value):
            print(f"   {alerta}")


# =====================================================================
# 10. PUNTO DE ENTRADA
# =====================================================================

def main() -> None:
    sistema = construir_sistema_demo()
    interfaz = InterfazConsola(sistema)
    interfaz.ejecutar()


if __name__ == "__main__":
    main()
