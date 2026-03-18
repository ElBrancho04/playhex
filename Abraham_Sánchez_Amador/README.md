# Smart Player para HEX

## Descripción General

Este proyecto implementa un jugador autónomo para el juego HEX basado en una combinación de **Monte Carlo Tree Search (MCTS)** y heurísticas específicas del dominio.

El objetivo es construir un agente competitivo que tome decisiones de alta calidad dentro de las restricciones de tiempo del torneo, equilibrando precisión estratégica y eficiencia computacional.

---

## Estrategia General

El comportamiento del jugador se estructura en dos fases principales:

### 1. Detección de Jugadas Forzadas

Antes de iniciar cualquier proceso de búsqueda, el agente verifica:

- Jugadas que producen una victoria inmediata
- Jugadas necesarias para bloquear una victoria del oponente

Si existe alguna de estas situaciones, se selecciona directamente la jugada correspondiente. Esto permite resolver de forma óptima los estados críticos sin incurrir en coste adicional de exploración.

---

### 2. Búsqueda mediante MCTS

En ausencia de jugadas forzadas, se emplea un algoritmo de **Monte Carlo Tree Search** enriquecido con heurísticas específicas de HEX que mejoran significativamente su rendimiento frente a una versión estándar.

---

## Heurísticas Principales

### Celdas Críticas

Se definen como aquellas que minimizan los caminos de conexión entre los lados del tablero.

Para su cálculo se utiliza una variante de Dijkstra basada en la **segunda distancia mínima**, lo cual permite modelar de forma más realista la interacción con el oponente, asumiendo que este puede bloquear el camino óptimo.

Estas celdas representan posiciones estratégicamente relevantes y son utilizadas para guiar tanto la expansión como las simulaciones.

---

### Celdas Centrales (Apertura)

Durante la fase inicial del juego, el agente prioriza posiciones cercanas al centro del tablero. Esto favorece una mayor conectividad potencial y flexibilidad en etapas posteriores de la partida.

---

## Simulación Guiada (Playout)

A diferencia del enfoque clásico de MCTS, que emplea simulaciones completamente aleatorias, este jugador utiliza simulaciones guiadas:

- Se priorizan celdas críticas y, en apertura, celdas centrales
- Se reduce el ruido en la evaluación de estados
- Se obtiene una estimación más estable del valor de cada jugada

---

### Factor de Confianza Decreciente

Para evitar un sesgo excesivo hacia las heurísticas iniciales, se introduce un mecanismo de ajuste dinámico:

- La influencia de las celdas críticas disminuye con la profundidad en el árbol MCTS
- También disminuye a medida que avanza el playout

La intuición es que estas heurísticas se calculan sobre el estado inicial del tablero, y su validez se degrada conforme la partida evoluciona.

---

## Mejoras sobre MCTS Clásico

### UCB1 con Varianza

Se emplea una variante de UCB1 que incorpora la varianza observada:

- Se incrementa la exploración en nodos con alta incertidumbre
- Se reduce el esfuerzo en nodos con comportamiento predecible

---

### Progressive Widening

El número de hijos explorados desde un nodo se limita en función de la cantidad de visitas:

- Se prioriza la exploración de movimientos prometedores
- Se evita expandir prematuramente jugadas de baja calidad

Esta técnica permite profundizar más en líneas relevantes antes de diversificar la búsqueda.

---

### Simulación Informada

Durante las simulaciones:

- Se priorizan jugadas estratégicas en lugar de selecciones uniformes
- Se consideran situaciones de jugadas forzadas en etapas avanzadas
- Se mantiene un equilibrio entre exploración y explotación

---

## Optimizaciones de Rendimiento

Para cumplir con las restricciones de tiempo del torneo, se incorporan varias optimizaciones:

- Uso de **Union-Find reversible (DSU)** para detección eficiente de victoria
- Cache de vecinos del tablero
- Minimización de copias del estado
- Control explícito del tiempo de ejecución

---

## Decisiones de Diseño

El diseño del agente responde a los siguientes principios:

- Reducir la aleatoriedad inherente al MCTS clásico
- Incorporar conocimiento específico del dominio de HEX
- Priorizar jugadas estratégicamente relevantes desde etapas tempranas
- Mantener eficiencia computacional bajo límites estrictos de tiempo

---

## Conclusión

La combinación de MCTS con heurísticas basadas en la estructura del tablero y caminos mínimos permite obtener un agente robusto y competitivo. Este enfoque mejora significativamente la calidad de las decisiones respecto a métodos puramente aleatorios, manteniendo un rendimiento adecuado para entornos de torneo.