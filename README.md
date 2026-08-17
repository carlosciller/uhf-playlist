# UHF Playlist

Playlist M3U8 de TDTChannels adaptada para UHF.

## URL para UHF

```text
https://chitichiti.github.io/uhf-playlist/tv-uhf.m3u8
```

EPG oficial:

```text
https://www.tdtchannels.com/epg/TV.xml.gz
```

## Qué hace la automatización

- Descarga diariamente la lista oficial de TDTChannels.
- Normaliza la cabecera M3U8 para mejorar la compatibilidad con UHF.
- Cruza automáticamente cada canal con los catálogos públicos de `iptv-org` y `tv-logo/tv-logos`.
- Cuando no encuentra coincidencia, prueba la imagen de TDTChannels y el icono de la web oficial del canal.
- Guarda una copia de cada logo resuelto en el propio repositorio.
- Reemplaza los enlaces externos de logos por URLs estables de GitHub Pages.
- Elimina del M3U los enlaces de imagen rotos cuando no existe una alternativa fiable.
- Conserva todos los canales y emisiones alternativas de la fuente.

Los logos ya descargados se mantienen para evitar que desaparezcan si Facebook, X u otro proveedor cambia sus direcciones. Los casos especiales pueden corregirse en `logo_overrides.json`, usando como clave el `tvg-id` o el nombre del canal y como valor una URL directa de imagen.

Fuente: [TDTChannels](https://www.tdtchannels.com/listas/).
