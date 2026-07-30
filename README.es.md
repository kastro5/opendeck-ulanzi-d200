*[English](README.md) · **Español***

# Plugin de Ulanzi D200X para OpenDeck

Un **plugin de dispositivo** para [OpenDeck](https://github.com/nekename/OpenDeck):
hace que la Ulanzi D200X aparezca como un deck normal dentro de OpenDeck, de
forma que puedas arrastrar sobre sus teclas, botones laterales y ruletas
cualquier acción de OpenDeck, venga del plugin que venga.

Esto no es un controlador independiente: mientras OpenDeck esté funcionando,
sustituye al daemon de `ulanzi_manager`. Usa uno u otro, no los dos a la vez.

## Qué expone

| Hardware | Hueco en OpenDeck | Notas |
|---|---|---|
| 12 pantallas cuadradas (filas 1–2 y las tres primeras de la fila 3) | Keypad 0–12 | iconos de 196×196 |
| la pantalla doble (abajo a la derecha) | Keypad 13 | ver más abajo |
| — | Keypad 14 | sin usar: es la mitad derecha de la tecla 13 |
| los 2 botones laterales pequeños | Touchpoint 1 y 2 (Keypad 15/16) | solo botones, sin pantalla |
| las 3 ruletas | Encoder 0–2 | giro y pulsación |

Son 14 pantallas en total, y por eso la rejilla se declara como 5×3 con una
celda muerta: OpenDeck solo sabe describir rejillas rectangulares, así que la
pantalla fusionada ocupa el hueco 13 y el 14 se deja vacío a propósito.

### La pantalla doble (hueco 13)

Lo que muestra esta pantalla es configurable. Pon encima la acción **Wide
screen** del propio plugin y su inspector de propiedades te ofrece:

| Modo | Qué muestra la pantalla |
|---|---|
| **Reloj** (por defecto) | el reloj integrado en el dispositivo |
| **Monitor del sistema** | los medidores de CPU / RAM / GPU del firmware |
| **Apagada** | negro |

El ajuste es global, no por tecla: se aplica a la pantalla ancha esté o no la
acción encima, así que también decide qué se ve cuando el hueco 13 está
**vacío**.

Si pones ahí cualquier **otra** acción, la pantalla pasa a modo imagen y
renderiza el icono de esa acción, con bandas negras para que no salga estirado.

En todos los casos la pantalla se puede pulsar y dispara `Keypad 13`.

El dispositivo no mide nada del equipo: el firmware dibuja los porcentajes que
llevara la última actualización de estado. El plugin lee `/proc/stat` y
`/proc/meminfo` para CPU y RAM, y `gpu_busy_percent` (amdgpu) o `nvidia-smi`
para la GPU; si no hay ninguno de los dos, el medidor de GPU se queda a cero.

## Limitaciones estéticas

Hay dos cosas de la maquetación en pantalla que no se pueden arreglar desde
aquí, porque un plugin de dispositivo solo puede declarar `rows`, `columns`,
`encoders`, `touchpoints`, `infobars` y `type`. Todo lo demás está fijo en el
frontend de OpenDeck (`src/components/DeviceView.svelte`):

* Los dos botones laterales se pintan a tamaño completo en una fila propia, en
  vez de a la mitad de tamaño y centrados junto a las ruletas.
* La pantalla doble se ve como el hueco 13 más un hueco 14 vacío, en vez de como
  una sola tecla que ocupe ambas celdas y el espacio entre ellas.

Las dos son pura maquetación. `Key.svelte` ya admite lienzos rectangulares y
escalado (los usa para la infobar de la Stream Deck Neo), así que cambiarlo
implicaría parchear y recompilar OpenDeck, o pedirlo como mejora upstream.

## Requisitos

Python 3 con tres paquetes:

```sh
# Arch / CachyOS
sudo pacman -S python-hidapi python-pillow python-websockets
# Debian / Ubuntu
sudo apt install python3-hid python3-pil python3-websockets
```

Si usas OpenDeck como Flatpak, instálalos **en el anfitrión**, no dentro del
sandbox: el plugin se relanza a sí mismo en el anfitrión con
`flatpak-spawn --host`, porque desde dentro del sandbox no se llega ni a
`/dev/hidraw*` ni a `hidapi`.

## Permisos del dispositivo (udev) — obligatorio

Por defecto `/dev/hidraw*` solo lo puede leer root, así que **el plugin no verá
la D200X hasta que una regla de udev dé acceso**. Este es, con diferencia, el
motivo más habitual de que «el dispositivo no aparece en OpenDeck».

OpenDeck instala su propia `40-streamdeck.rules`, pero aquí *no* sirve: solo
cubre el vendor ID de Elgato (`0fd9`), no el de Ulanzi (`2207`).

```sh
sudo cp 60-ulanzi-d200x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

La regla es una sola línea, con la misma forma que las que OpenDeck trae para
sus propios dispositivos:

```
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2207", ATTRS{idProduct}=="0019", MODE="0660", TAG+="uaccess"
```

No hace falta ninguna regla `SUBSYSTEM=="usb"`: `python-hidapi` usa el backend
hidraw (`libhidapi-hidraw.so`), así que solo se abre el nodo hidraw. Añádela
únicamente si has compilado hidapi contra libusb a propósito.

Las reglas de udev se aplican cuando ocurre un evento de dispositivo, así que
**si la D200X ya estaba enchufada, desenchúfala y vuelve a enchufarla** (o
reinicia).

### Comprobación

```sh
$ ls -l $(python3 -c "import hid;print(' '.join(d['path'].decode() for d in hid.enumerate(0x2207,0x0019)))")
crw-rw----+ 1 root root 243, 5 ... /dev/hidraw5
crw-rw----+ 1 root root 243, 6 ... /dev/hidraw6
```

El dispositivo expone **dos** interfaces hidraw y la regla cubre las dos; el
plugin usa la primera. Lo que importa es el `+` del final: es la ACL de
`uaccess` que da acceso de lectura y escritura a tu sesión. Confírmalo con
`getfacl /dev/hidraw5`, donde deberías ver `user:<tu_usuario>:rw-`.

`install.sh` hace esta comprobación por ti y avisa si el nodo no es escribible.

Si tu sistema no usa systemd-logind, `uaccess` no hace nada. Añade
`GROUP="input"` a la regla y asegúrate de pertenecer a ese grupo.

### Por qué no `MODE="0666"`

Muchas guías usan `MODE="0666"`, que funciona pero deja el dispositivo legible y
escribible por todo el mundo: cualquier proceso local podría entonces leer tus
pulsaciones y controlar las pantallas. `TAG+="uaccess"` da acceso solo al
usuario con sesión iniciada en el asiento local, que es más seguro y es la
convención moderna.

## Instalación

```sh
sudo cp 60-ulanzi-d200x.rules /etc/udev/rules.d/   # ver arriba; hazlo primero
sudo udevadm control --reload-rules && sudo udevadm trigger

./install.sh          # copia al directorio de plugins de OpenDeck
./install.sh --link   # enlace simbólico, para desarrollo
./install.sh --uninstall
```

Después reinicia OpenDeck.

## Cómo funciona

OpenDeck renderiza cada tecla a una data URL en JPEG y la envía con `setImage`.
La D200X no acepta imágenes tecla a tecla: el firmware solo admite un **paquete
ZIP** con `manifest.json` más todos los iconos, escrito por HID en bruto en
paquetes de 1024 bytes. Por eso el plugin:

1. Decodifica cada `setImage`, lo escala a 196×196 (392×196 comprimido para la
   pantalla ancha) y lo cachea.
2. Agrupa las ráfagas de actualizaciones (`FLUSH_DEBOUNCE`) y limita la
   frecuencia de envíos (`MIN_BUNDLE_INTERVAL`) para no saturar el firmware.
3. Reconstruye el paquete rellenando `dummy.txt` hasta que ningún byte `0x00` ni
   `0x7c` caiga en un límite de paquete: es un fallo de parseo del firmware con
   el que también topa el daemon original.

Una página llena de teclas vivas (un reloj, un monitor del sistema) supone un
paquete cada pocos segundos, y todo lo que el firmware repinte en ese momento
parpadea. Por eso, cuando es el firmware quien dibuja la pantalla ancha (reloj o
monitor del sistema), esa celda no lleva entrada en el manifiesto, y el modo
solo se reenvía cuando cambia de verdad. Reenviarlo con un temporizador hace que
el firmware repinte el reloj, y eso se ve como un parpadeo.

El dispositivo lleva la hora por su cuenta, así que basta con ponérsela una vez
al conectar. Lo único que hay que alimentar es el monitor del sistema, cada dos
segundos.

Los informes de entrada se decodifican en el mismo hilo HID y se reenvían como
`keyDown` / `keyUp` / `encoderChange` / `encoderDown` / `encoderUp`.

### Gestión de reconexiones

Mientras la D200X digiere un paquete grande, resetea brevemente su interfaz USB,
lo cual es indistinguible de un desenchufe. Por eso el hilo HID reabre el
descriptor en silencio y solo informa a OpenDeck de una desconexión cuando el
dispositivo lleva 30 segundos ausente. Al recuperarlo reenvía su paquete
cacheado en lugar de pedirle a OpenDeck que vuelva a renderizar: pedir un
rerender en cada reset es justo lo que convirtió esto en un bucle infinito en un
intento anterior.

## Resolución de problemas

**El dispositivo no aparece en OpenDeck.** Por orden de probabilidad:

1. **Falta la regla de udev** — mira [Permisos del dispositivo](#permisos-del-dispositivo-udev--obligatorio).
   Acuérdate de volver a enchufar el dispositivo después. Es la causa habitual.
2. **Faltan paquetes de Python.** `install.sh` lo comprueba y te dice cuáles.
3. **Plugin instalado en el directorio equivocado.** Un OpenDeck nativo lee
   `~/.config/opendeck/plugins/`; el Flatpak lee
   `~/.var/app/me.amankhanna.opendeck/config/opendeck/plugins/`. `install.sh`
   elige el que corresponde al OpenDeck que esté en marcha.

**El dispositivo aparece pero las pantallas siguen en negro.** Busca
`Pushed icon bundle` en el log. Si esa línea no sale nunca, OpenDeck no está
enviando imágenes; si sale pero las pantallas no cambian, hay algo más hablando
con el dispositivo: asegúrate de que el daemon de `ulanzi_manager` no está
funcionando.

**Solo un proceso puede controlar el dispositivo.** Si además tienes instalado
otro plugin de dispositivo de la familia D200 (por ejemplo
`com.glmagalhaes.ulanzi.d200.sdPlugin`), desactiva uno de los dos: abren el
mismo nodo hidraw y se pisan las pantallas mutuamente. `install.sh` te avisa si
encuentra alguno.

## Depuración

El plugin escribe sus logs por stderr, que OpenDeck captura. La ruta depende de
cómo hayas instalado OpenDeck:

```sh
# paquete nativo (opendeck-bin y similares)
tail -f ~/.local/share/opendeck/logs/plugins/com.ulanzi.d200x.sdPlugin.log
# Flatpak
tail -f ~/.var/app/me.amankhanna.opendeck/data/opendeck/logs/plugins/com.ulanzi.d200x.sdPlugin.log
```

Define `D200X_DEBUG=1` en el entorno para una salida más detallada.

## Notas del protocolo

| Comando | Valor | Para qué |
|---|---|---|
| `SET_BUTTONS` | `0x0001` | paquete ZIP de iconos y manifiesto |
| `SET_SMALL_WINDOW` | `0x0006` | modo de la pantalla ancha: `0` stats, `1` reloj, `2` imagen |
| `SET_BRIGHTNESS` | `0x000a` | 0–100 |
| `SET_LABEL_STYLE` | `0x000b` | desactivado aquí: OpenDeck ya incrusta los títulos en la imagen |
| `IN_BUTTON` | `0x0101` / `0x0102` | entrada de teclas y ruletas |

Índices de hardware: pantallas `0–13`, botones laterales `15`/`16`, ruletas
`17`/`18`/`19` (byte de evento de ruleta: `0` soltar, `1` pulsar, `2` girar a la
izquierda, `3` girar a la derecha).
