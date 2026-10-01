# Especificación: herramienta Bisel / Redondeo (estilo Blender) para IngeTrazo

> Documento de requisitos para desarrollar una herramienta de bisel/redondeo
> equivalente al **Bevel** de Blender (`Ctrl+B` / `Ctrl+Shift+B`), con
> control completo por teclado y ratón y un **panel temporal de ajustes**
> («Adjust Last Operation», `F9` en Blender). Incluye además la propuesta de
> una herramienta aparte para **editar la cantidad de segmentos** de curvas y
> figuras planas.

---

## 0. Punto de partida: lo que ya hace «Fillet 3D»

`tools/fillet.py` + `core/fillet.py` ya resuelven bastante:

| Ya existe | Detalle |
|---|---|
| Redondeo de aristas entre exactamente 2 caras | Tira de quads sobre el cilindro tangente a ambas caras |
| Radio con el cursor | Distancia perpendicular del cursor a la línea de la arista |
| Radio por teclado (VCB) | Escribir valor + `Enter` |
| Segmentos `Ns` | Escribir `12s` en el VCB |
| Cadenas | Dos aristas redondeadas que se encuentran → corte a inglete (plano bisector) |
| Esquinas de caja | Tres aristas redondeadas → parche esférico |
| Rechazo seguro | Si no se puede, dice por qué y no toca el modelo |
| Vista previa en vivo | Caras + curvas de la tira |
| Deshacer | `SnapshotMutation` en el historial |
| Suavizado | Costuras y líneas tangentes marcadas *soft* |

**Lo que falta** respecto a Blender (se detalla abajo): bisel de **vértices**,
**forma del perfil** (cóncavo/convexo/recto), **tipos de medida** (offset,
ancho, profundidad, porcentaje), **chaflán** explícito, **clamp overlap**
(limitar en lugar de rechazar), vértices con 4+ aristas, teclas modales
(`S`, `P`, `V`, `C`, rueda, `Shift`, `Ctrl`…), **panel de ajustes posterior**,
perfil personalizado, opciones de material/inglete, y bisel 2D de esquinas de
figuras planas.

---

## 1. Alcance de la herramienta

### 1.1 Modos de afectación (`V` alterna)
1. **Aristas** (por defecto): redondea/chaflana aristas de sólidos o de
   superficies.
2. **Vértices**: recorta el vértice.
   - En una **figura plana** (cara 2D): redondea/chaflana la **esquina** del
     polígono (el «fillet 2D»). Hoy esto lo hace el Arco tangente-tangente
     de una esquina a la vez; aquí se haría a varias esquinas a la vez, con
     el mismo radio y segmentos.
   - En un **sólido**: corta la punta del vértice (esquina de caja → triángulo
     o casquete esférico según segmentos y perfil).

### 1.2 Entrada / selección
- Usar la **selección actual** si contiene aristas (o vértices / caras
  según el modo). Si hay **caras** seleccionadas, biselar su contorno.
- Si no hay selección: clic sobre una arista/vértice (con resaltado *hover*).
- `Shift+clic` durante la fase de elección añade/quita aristas antes de
  empezar a dimensionar.
- Doble clic sobre una arista: selecciona el **bucle tangente** (toda la
  cadena de aristas de una curva o contorno) — equivalente a seleccionar el
  borde completo de una losa.
- Curvas existentes (`edge.curve`): al tocar un segmento se toma toda la
  curva, como ya hace la selección.
- Dentro de grupos/componentes: actuar sobre la malla del grupo en edición
  (igual que Push/Pull con `mesh=`).

---

## 2. Parámetros (los que aparecen en el panel de ajustes)

| Parámetro | Tipo | Por defecto | Notas |
|---|---|---|---|
| **Afecta** | Aristas / Vértices | Aristas | Tecla `V` |
| **Tipo de medida** | Offset · Ancho · Profundidad · Porcentaje · Absoluto · **Radio** | Radio | Tecla `M` cicla. «Radio» es el que usa hoy Fillet 3D y es el natural en arquitectura |
| **Cantidad** | longitud (o % si Porcentaje) | último usado | Arrastre del ratón o teclado |
| **Segmentos** | entero ≥ 1 | 8 | `1` = **chaflán**. `S` + ratón, rueda, o `Ns` en el VCB |
| **Forma (perfil)** | 0.0 – 1.0 | 0.5 | 0.5 = circular; 1.0 = esquina viva hacia fuera (convexo extremo); 0.0 = cóncavo; 0.25 ≈ recto/plano con segmentos. Tecla `P` + ratón |
| **Tipo de perfil** | Superelipse · Personalizado | Superelipse | Tecla `Z`. Personalizado = editor de curva (fase posterior) |
| **Limitar solapes (Clamp)** | sí/no | sí | Tecla `C`. Si sí: la cantidad se **limita** al máximo posible en lugar de rechazar |
| **Deslizar sobre bucle** | sí/no | sí | Mantiene los nuevos vértices sobre las aristas existentes cuando es posible |
| **Inglete exterior** | Vivo · Parche · Arco | Vivo | Tecla `O`. Qué hacer donde se juntan aristas biseladas en ángulo convexo |
| **Inglete interior** | Vivo · Arco | Vivo | Tecla `I` |
| **Dispersión (spread)** | longitud | 0.1 | Solo con ingletes en Arco |
| **Tipo de intersección** | Rejilla (grid fill) · Corte (cutoff) | Rejilla | Cómo se cierra un vértice donde llegan 3+ aristas biseladas (hoy: esfera para 3, rechazo para 4+) |
| **Material** | heredar · índice | heredar | Material de la nueva tira (`M`… en Blender va con otra tecla; aquí botón en panel) |
| **Suavizar (soft)** | sí/no | sí | Marcar costuras internas *soft* (como hoy) |
| **Endurecer normales** | sí/no | no | Tecla `H`. Normales de las caras planas vecinas sin contaminar |
| **Marcar costura / arista viva** | sí/no | no | `U` / `K`. Útil luego para texturas y exportación |

> **Regla de oro**: todo parámetro del panel debe poder cambiarse también
> durante la operación modal con una tecla, y todo valor numérico debe
> poder escribirse.

---

## 3. Interacción modal (teclado + ratón)

### 3.1 Flujo
1. Activar herramienta (botón, menú, búsqueda `F3`, o atajo; propuesta:
   **`Ctrl+B`** aristas, **`Ctrl+Shift+B`** vértices).
2. Si hay selección válida, entra **directamente** en modo de dimensionado;
   la distancia inicial del ratón queda como referencia.
3. Mover ratón → cambia la **cantidad** (vista previa en vivo).
4. `Clic izquierdo` / `Enter` → confirmar. `Clic derecho` / `Esc` → cancelar
   y dejar el modelo intacto.
5. Al confirmar aparece el **panel de ajustes** (sección 4).

### 3.2 Control de la cantidad con el ratón
- Modo actual («distancia a la línea de la arista») se mantiene como opción,
  pero añadir el modo **Blender**: cantidad proporcional a la distancia del
  cursor al **centro de la selección en pantalla**, relativa a la distancia
  inicial. Es más estable en vistas oblicuas y con muchas aristas.
- **`Shift` mantenido** → precisión ×0.1 (movimiento fino).
- **`Ctrl` mantenido** → saltos por incrementos (por ejemplo 1 cm / 5 cm
  según escala de la vista o la precisión de unidades del modelo).
- Línea guía punteada desde el centro hasta el cursor (como Blender) y
  etiqueta flotante con el valor (`value_label` ya existe).

### 3.3 Teclas durante la operación

| Tecla | Acción |
|---|---|
| Ratón | Cantidad |
| `S` | El ratón pasa a controlar **segmentos** (volver con `A`/`S` otra vez) |
| Rueda ↑ / ↓ | Segmentos +1 / −1 |
| `+` / `-` del teclado numérico | Segmentos +1 / −1 |
| `P` | El ratón controla la **forma del perfil** |
| `V` | Alternar Aristas / Vértices |
| `M` | Ciclar tipo de medida |
| `C` | Clamp overlap sí/no |
| `O` / `I` | Ciclar inglete exterior / interior |
| `Z` | Tipo de perfil Superelipse / Personalizado |
| `H` | Endurecer normales |
| `U` / `K` | Marcar costura / arista viva |
| `Tab` | Pasar el foco de entrada numérica al siguiente campo (cantidad → segmentos → perfil) |
| Dígitos | Entrada numérica directa del campo activo |
| `Backspace` | Borrar dígito; si vacío, volver al control por ratón |
| `Enter` / clic izq. | Confirmar |
| `Esc` / clic der. | Cancelar |

### 3.4 Entrada numérica
- Escribir **sin abrir nada**: los dígitos van al VCB (ya existe la caja de
  medidas).
- Aceptar **unidades** (`5cm`, `2"`, `0.1m`) — `core/units` ya las interpreta.
- Aceptar **expresiones** simples (`10cm/2`, `3*2.5`).
- Sufijos: `12s` = segmentos (ya existe), `0.3p` = perfil, `25%` = porcentaje.
- Varios valores separados por `;` → `5cm;8s;0.5p` (cantidad, segmentos,
  perfil) en un solo `Enter`.

### 3.5 Barra de estado / encabezado
Mientras dura la operación, la barra de estado (`views/status_hints.py`)
muestra en una línea todas las teclas y su valor actual, p. ej.:

`Bisel · Radio 5 cm · Segmentos 8 [S/rueda] · Perfil 0.50 [P] · Aristas [V] · Clamp ✓ [C] · Inglete Vivo [O] · Shift fino · Ctrl pasos`

### 3.6 Vista previa
- Malla resultante en vivo (ya existe con `preview_faces`).
- Si el cálculo falla para ese valor, la vista previa se pone **en rojo** en
  la zona conflictiva con el motivo, pero la operación sigue abierta (el
  usuario puede corregir el valor sin empezar de nuevo).
- Con Clamp activo, al llegar al máximo el valor se queda fijo y la
  etiqueta indica `(máx.)`.
- El cálculo debe ser rápido: cachear el plan por clave (ya existe
  `_plan_key`) y, si una vista previa tarda >30 ms, calcular con menos
  segmentos durante el arrastre y el número real al soltar.

---

## 4. Panel temporal de ajustes («Ajustar última operación»)

Esta es la pieza que más valor da y conviene hacerla **genérica para todas
las herramientas**, no solo para el bisel.

### 4.1 Comportamiento
- Aparece al confirmar una operación, como panel plegable flotante en la
  esquina inferior izquierda del visor (o como pestaña en la bandeja derecha;
  recomendado: flotante, semitransparente, no roba foco).
- Muestra **todos los parámetros** de la sección 2 con controles adecuados:
  campo numérico con unidades y arrastre (*slider* horizontal al arrastrar
  sobre el número), *spinbox* para segmentos, desplegables, casillas.
- **Cada cambio rehace la operación** con los nuevos parámetros sobre el
  estado anterior: deshacer el último comando → volver a ejecutar con los
  parámetros nuevos → sustituir la entrada del historial (no apilar una
  nueva por cada clic del panel).
- Desaparece (o queda deshabilitado) en cuanto se hace **cualquier otra
  modificación** al modelo, se cambia de herramienta o se deshace.
- `F9` (propuesta) lo reabre en la posición del ratón mientras la última
  operación siga siendo rehacible.
- Recordar si estaba plegado o desplegado (preferencia por usuario).
- Botón «Restablecer valores por defecto» por parámetro (clic derecho) y
  general.

### 4.2 Requisitos técnicos para que funcione
1. **Operación parametrizada**: cada herramienta compatible expone
   - `operator_params()` → lista de descriptores
     `(clave, etiqueta, tipo, valor, mín, máx, paso, unidades, opciones)`;
   - `execute(scene, entrada, params)` puro, que **no dependa del estado
     de la herramienta** (hoy el cierre del `SnapshotMutation` captura el
     `plan`, que a su vez guarda referencias a objetos `Edge`).
2. **Entrada estable**: al deshacer, el *snapshot* puede recrear los objetos
   `Edge`/`Vertex`, así que la entrada debe guardarse como claves estables
   (posiciones de los dos extremos redondeadas, como `_key()` en
   `core/fillet.py`) y re-resolverse tras el deshacer.
3. **Comando reemplazable** en `core/history.py`: p. ej.
   `history.redo_last_with(params)` que hace `undo()` + nueva ejecución +
   sustitución atómica de la entrada; si la nueva ejecución falla, se
   restaura el resultado anterior y el panel muestra el error junto al
   parámetro.
4. **Panel autogenerado** a partir de los descriptores (un único widget
   `views/adjust_panel.py`), para que Círculo, Arco, Polígono, Push/Pull,
   Equidistancia (Offset), Sígueme, Mover/Rotar con copias (array) lo
   aprovechen sin código de interfaz propio. Ejemplos inmediatos:
   - Círculo: radio, segmentos, ¿con cara?
   - Push/Pull: distancia, crear nuevo (`Ctrl`).
   - Rotar/Mover copia: número de copias, distancia/ángulo total o entre
     copias.
5. **Traducciones** con `tr()` y textos de ayuda (*tooltip*) por parámetro.

---

## 5. Comportamiento geométrico detallado

### 5.1 Casos que debe resolver (ampliando los actuales)
| Caso | Hoy | Objetivo |
|---|---|---|
| Arista convexa entre 2 caras | ✓ | ✓ |
| Arista cóncava (rincón interior) | revisar | ✓ (redondeo hacia dentro, añade material) |
| Cadena de 2 aristas | ✓ inglete | ✓ + opción inglete en arco |
| Esquina de 3 aristas | ✓ esfera | ✓ + perfil ≠ 0.5 con superelipse y opción «corte» |
| Vértice con 4+ aristas biseladas | rechazo | **Rejilla** (grid fill tipo Blender) o polígono de **corte** |
| Vértice con caras extra | rechazo | resolver si las caras extra no son tocadas por la tira |
| Arista abierta (borde de superficie) | sección perpendicular | ✓ |
| Arista sobre curva (cilindro) | — | biselar todo el contorno de una vez (bucle tangente) |
| Radio mayor que la cara | rechazo | con Clamp: limitar; sin Clamp: rechazo con motivo |
| Esquinas de figura plana (modo vértices) | Arco de 1 en 1 | todas las seleccionadas a la vez |

### 5.2 Perfil superelipse
Sección del perfil en coordenadas locales (u, v) entre los dos puntos de
tangencia: `|u|^r + |v|^r = 1` con `r` derivado de *Forma*
(0.5 → r = 2 círculo; 1 → r → ∞ esquina; 0.25 → r = 1 recto; 0 → r → 0
cóncavo). Los segmentos se distribuyen uniformemente en longitud de arco.

### 5.3 Garantías
- Mantener la **guarda de hermeticidad**: nunca dejar un sólido abierto.
- Mantener materiales y capas de las caras vecinas; la tira hereda el
  material común (como hace hoy `_shared_attrs`) o el elegido.
- Coordenadas UV de texturas continuas en las caras recortadas.
- Las curvas resultantes (arcos en las tapas) etiquetadas como `curve`
  para que luego sean editables por la herramienta de segmentos (sección 6).
- Guardar en las caras/aristas generadas los **metadatos de la operación**
  (centro, eje, radio, perfil, segmentos) para poder re-editar más tarde.

---

## 6. Herramienta aparte: editar cantidad de segmentos

**Sí, vale la pena**, y encaja muy bien con el resto. Blender no lo tiene
para mallas ya creadas. En IngeTrazo sería un diferencial.

### 6.1 Qué hace
Cambiar el número de segmentos de una curva ya dibujada (círculo, arco,
polígono regular, arcos de un redondeo) **sin redibujarla**, manteniendo
centro, radio, ángulos, puntos extremos y la cara que encierra.

### 6.2 Interacción
- Seleccionar una o varias curvas (clic en cualquier segmento ya toma toda la
  curva gracias a `edge.curve`).
- Activar la herramienta (o desde **Información de entidad**: campo
  «Segmentos» editable cuando la selección es una curva).
- Rueda / `+` `-` → segmentos ±1, con vista previa en vivo.
- Escribir `24` + `Enter` (o `24s`).
- Panel de ajustes (sección 4) con: segmentos, modo «mismo número» o
  «longitud máxima de segmento» (p. ej. 5 cm → calcula N automáticamente),
  y «mantener vértices extremos».
- Atajo propuesto: `Alt+S` o desde `F3`.

### 6.3 Requisitos técnicos
1. **Metadatos de curva**: hoy las aristas solo guardan un id `curve`, no la
   geometría. Hay que guardar por id: tipo (círculo/arco/polígono), centro,
   normal, radio, ángulo inicial y final, sentido. Persistirlo en el formato
   de archivo y en `EDGE_FLAG_NAMES`/serialización.
2. **Curvas antiguas o importadas (DXF u otros formatos)** sin metadatos: **ajustar** un
   círculo por los vértices (mínimos cuadrados) y aceptar solo si el error es
   menor que una tolerancia; si no, avisar «no es un arco».
3. **Reconstrucción**: quitar los segmentos viejos, insertar los nuevos con
   el mismo id de curva, y reconstruir la(s) cara(s) que usaban ese contorno
   (las caras planas se re-detectan; ya existe `build_add_edges` con
   `detect_faces`).
4. **Curvas extruidas** (cilindros, orificios, redondeos): fase 2. Exige
   regenerar las caras laterales (una por segmento) a lo largo de la
   extrusión; viable si la superficie lateral es una extrusión recta de la
   curva (detectar caras laterales *soft* entre dos copias paralelas de la
   curva). Si no se puede, rechazar con motivo, como hace Fillet 3D.
5. Deshacer en un único paso.

---

## 7. Plan de desarrollo por fases (recomendado)

1. **Panel de ajustes genérico** + historial reemplazable, probado primero
   con Círculo (radio/segmentos) — es lo de menor riesgo geométrico y deja
   la infraestructura lista.
2. **Teclas modales del Fillet 3D actual**: `S`, rueda, `Shift` fino, `Ctrl`
   pasos, `C` clamp, entrada `;` múltiple, barra de estado completa,
   `Ctrl+B`. Conectarlo al panel.
3. **Clamp overlap** (limitar en vez de rechazar) y **chaflán** explícito
   (segmentos = 1 + tipos de medida Offset/Ancho/Profundidad).
4. **Modo vértices**: primero esquinas de figuras planas (2D), luego
   vértices de sólidos.
5. **Perfil superelipse** (`P`) y ingletes (`O`/`I`).
6. **Vértices con 4+ aristas** (rejilla/corte) y caras extra.
7. **Editar segmentos**: metadatos de curva → curvas planas → curvas
   extruidas.
8. Perfil personalizado (editor de curva) y extras (`H`, `U`, `K`).

### Pruebas a añadir (siguiendo `tests/test_fillet*.py`)
- Cada tecla modal cambia el parámetro correcto y la vista previa.
- Panel: cambiar un parámetro deja **una sola** entrada en el historial;
  `Ctrl+Z` vuelve al modelo original.
- Clamp: la cantidad nunca supera el máximo y el sólido sigue hermético.
- Perfil 0.5 coincide con el resultado actual del Fillet 3D (no regresión).
- Editar segmentos: círculo 24 → 12 → 48 conserva centro, radio y la cara;
  arco conserva extremos; curva importada no circular se rechaza.
