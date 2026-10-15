*[English](CHANGELOG.md) · **Español***

# Registro de cambios

## 1.3.1 — 2026-10-15

### Cambiado

- **El zip de Linux ya no necesita Python.** Lleva una compilación autónoma,
  como el exe de Windows, así que instalar desde el catálogo o desde la página
  de versiones funciona sin `hidapi`, `pillow` ni `websockets` en el sistema.
  `launch.sh` ejecuta esa compilación si está, y si no el `python3` del sistema
  (una copia del código instalada con `install.sh`). La compilación usa
  `/dev/hidraw*` como antes, así que sirve la misma regla udev.
- **La regla udev va dentro del zip**, así que una instalación desde el zip no
  necesita el repositorio para configurarla.

## 1.3.0 — 2026-10-15

### Cambiado

- **Nuevo identificador del plugin: `dev.kastro5.ulanzi-d200`** (antes
  `com.ulanzi.d200x`, heredado del proyecto original y con el nombre de la propia
  Ulanzi). Prepara el plugin para el catálogo de plugins de OpenDeck. Los
  identificadores de dispositivo no cambian, así que perfiles y teclas siguen
  igual. Al arrancar por primera vez, el plugin recupera los ajustes globales
  anteriores (modelo y modo de la pantalla ancha). Los instaladores borran la
  copia antigua; si no, quita `com.ulanzi.d200x.sdPlugin` en la pestaña Plugins
  de OpenDeck, porque las dos reclamarían el dispositivo. Una acción *Pantalla
  ancha* puesta en una tecla hay que volver a añadirla.
- **El autor pasa a ser `kastro5`**; el README da crédito al proyecto original.
- **Los zip de cada versión sirven para Windows y Linux.** El de cada modelo
  lleva el exe de Windows y el lanzador de Linux; se llaman
  `opendeck-ulanzi-<modelo>-v<versión>.zip`.

### Añadido

- **Distribución explícita del dispositivo** para las versiones de OpenDeck que
  la admiten ([nekename/OpenDeck#359](https://github.com/nekename/OpenDeck/pull/359),
  `layoutVersion` 1): la pantalla ancha se describe como una sola tecla que
  ocupa dos celdas, y los botones laterales de la D200X a media altura. OpenDeck
  sin modificar ignora estos campos y sigue dibujando la cuadrícula normal.

## 1.2.2 — 2026-10-14

### Cambiado

- **El consumo de CPU en reposo es ahora prácticamente nulo.** El hilo HID
  consultaba la entrada cada 5 ms y se despertaba unas 200 veces por segundo
  (alrededor de un 0,4 % de un núcleo con el deck en reposo). Ahora espera la
  entrada con una lectura bloqueante que expira cada 100 ms. Las pulsaciones se
  detectan en cuanto llegan.

## 1.2.1 — 2026-10-14

### Arreglado

- **El deck volvía al logo de arranque de Ulanzi tras menos de un minuto sin
  actividad.** El firmware da por desaparecido a un host que no envía nada, y en
  modo reloj el plugin no enviaba nada una vez subidos los iconos. Ahora el
  plugin reenvía el brillo actual siempre que lleve 5 segundos sin escribir. Esta
  señal de vida no redibuja nada, a diferencia de repetir el modo reloj, que
  parpadea.

## 1.2.0 — 2026-10-14

### Añadido

- **Soporte para Windows.** `install.ps1` genera un `d200x_plugin.exe`
  autónomo y lo instala en OpenDeck. En Windows, los reports de salida llevan el
  byte de report ID que exige la pila HID, se abre explícitamente la interfaz 0 y
  la pantalla de estadísticas lee CPU y RAM con `psutil`.
- **Soporte para la D200H.** Comparte ID USB y protocolo con la D200X, pero no
  tiene ruletas ni botones laterales. El modelo se elige con
  `install.ps1 -Model d200h` o desde los ajustes de la acción Pantalla ancha.
  Cada modelo se registra como un dispositivo distinto en OpenDeck, con sus
  propios perfiles.

## 1.1.3 — 2026-08-05

### Arreglado

- **La pantalla ancha arrancaba como un monitor del sistema congelado.** Con el
  reloj seleccionado, el dispositivo empezaba en su pantalla por defecto —los
  medidores, clavados a cero— hasta que se cambiaba el ajuste y se volvía a
  poner. El fondo negro que la 1.1.2 pinta al conectar es un paquete que nombra
  la celda ancha, y pintar esa celda saca al firmware del modo reloj y del modo
  monitor; el modo solo se enviaba cuando *cambiaba*, así que nadie lo volvía a
  poner, y los ceros eran los que llevaba aquel único comando. Ahora el modo se
  reafirma detrás de cualquier paquete que pinte la celda.
- El modo de la pantalla ancha aparece ya en el log del plugin, que hasta ahora
  no decía nada de él.

## 1.1.2 — 2026-08-01

### Arreglado

- **Parpadeo ocasional de todo el dispositivo.** El firmware interpreta mal un
  paquete cuando un byte `0x00` o `0x7c` cae en un límite de 1024 bytes, así que
  el paquete se reconstruye con rellenos distintos hasta que el reparto sale
  limpio; pero se rendía tras 31 intentos y lo enviaba igualmente mal formado.
  Una página con teclas vivas genera unos 217 KiB, lo que deja ~216 bytes en un
  límite y apenas un 8 % de repartos limpios, de modo que aproximadamente uno de
  cada trece envíos salía mal formado: con un paquete cada tres segundos, un
  fallo visible más o menos cada minuto. La búsqueda llega ahora a 200 intentos,
  lo que no cuesta nada en el caso normal (hacen falta unos doce) y hace que
  rendirse sea prácticamente imposible.

## 1.1.1 — 2026-08-01

### Arreglado

- **La pantalla ancha conservaba lo que hubiera detrás del reloj.** El firmware
  dibuja el reloj y los medidores encima de esa celda en lugar de limpiarla
  antes, y la 1.1.0 dejó de nombrarla en el paquete para acabar con el
  parpadeo, así que tampoco la limpiaba nadie más. Si el dispositivo se había
  quedado sin corriente, su logo de arranque seguía viéndose por debajo de la
  hora; con el icono de una acción que hubiera estado en esa tecla pasaba lo
  mismo. Ahora el plugin pinta un fondo negro la primera vez que se hace cargo
  de la celda y después vuelve a no tocarla, de modo que el parpadeo no
  reaparece.

## 1.1.0 — 2026-07-31

### Añadido

- **Pantalla ancha configurable.** Nueva acción **Wide screen**
  (`com.ulanzi.d200x.widescreen`) con un inspector de propiedades donde eliges qué
  muestra la tecla doble de abajo a la derecha: el **reloj** integrado del
  dispositivo (por defecto), un **monitor del sistema** o **apagada** (en negro).
  La elección es un ajuste global del plugin, así que también manda mientras la
  tecla está vacía; si pones ahí cualquier otra acción, se sigue viendo su icono.
  El inspector sale en español o en inglés según el idioma de OpenDeck.
- **Valores reales de CPU / RAM / GPU** para el monitor del sistema, leídos de
  `/proc/stat`, `/proc/meminfo` y `gpu_busy_percent` (amdgpu) o `nvidia-smi`.
  Antes los medidores recibían ceros fijos, porque el dispositivo no mide nada
  por sí mismo: solo dibuja lo que se le manda.

### Corregido

- **Parpadeo de la pantalla ancha.** Toda celda nombrada en el `manifest.json` de
  un paquete se repinta cuando ese paquete llega, así que el reloj se tapaba —
  dejando ver un instante lo que había debajo — en cada envío, lo que con teclas
  vivas en la página significaba cada pocos segundos. Ahora esa celda se queda
  fuera del paquete siempre que sea el firmware quien la dibuja.
- **Parpadeo del reloj.** El modo de la pantalla ancha se reenviaba cada dos
  segundos y cada orden obligaba al firmware a repintar. Ahora solo se envía
  cuando el modo cambia de verdad; el dispositivo lleva la hora por su cuenta.

### Cambiado

- `install.sh` ya no copia `__pycache__` al directorio del plugin.

## 1.0.0

Primera versión: la D200X se registra en OpenDeck como un dispositivo de 5×3 —14
pantallas (las dos de abajo a la derecha son una sola pantalla doble), los dos
botones laterales como touchpoints y las tres ruletas como encoders— con los
iconos empaquetados en el ZIP que espera el firmware, las reconexiones USB
absorbidas en silencio y una única regla de udev para el acceso a hidraw.
