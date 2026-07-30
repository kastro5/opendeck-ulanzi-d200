*[English](CHANGELOG.md) · **Español***

# Registro de cambios

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
