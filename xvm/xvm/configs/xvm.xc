{
  // Version of the config. Do not remove or change it unnecessarily.
  // Версия конфига. Не удаляйте и не изменяйте её без необходимости.
  "configVersion": "5.1.0",

  // Version of the editor.
  // Версия редактора.
  "editorVersion": "0.80",

  // Language used in mod
  // "auto" - automatically detect language from game client,
  // or specify file name located in res_mods/xvm/l10n/ (ex: "en")
  // Используемый язык в моде
  // "auto" - автоматически определять язык клиента игры,
  // или укажите имя файла в папке res_mods/xvm/l10n/ (например, "en")
  "language": "auto",

  // Game Region
  // "auto" - automatically detect game region from game client,
  // or specify one of: "RU", "EU", "NA", "SG", "VTC", "KR"
  // Регион (игровой кластер)
  // "auto" - автоматически определять регион из клиента игры,
  // или укажите один из: "RU", "EU", "NA", "SG", "VTC", "KR"
  "region": "auto",

  // Common config options. All settings information in the mod not being used.
  // Общие параметры конфига. Все параметры информационные, в моде не используются.
  "definition": {
    // Config author.
    // Автор конфига.
    "author": "Omegaice",

    // Config description.
    // Описание конфига.
    "description": "Example XVM configuration",

    // Address to config updates.
    // Адрес, где выкладываются обновления конфига.
    "url": "",

    // Config last modified.
    // Дата последней модификации конфига.
    "date": "25.04.2014",

    // Supported version of the game.
    // Поддерживаемая версия игры.
    "gameVersion": "0.9.0",

    // The minimum required version of the XVM mod.
    // Минимально необходимая версия мода XVM.
    "modMinVersion": "5.0.0"
  },

  // Minimap.
  // Миникарта.
  "minimap": {
    // false - Disable.
    // false - отключить.
    "enabled": true,
    // Map image transparency.
    // Прозрачность изображения карты.
    "mapBackgroundImageAlpha": 100,
    // Self icon transparency. White pointing arrow.
    // Прозрачность своей иконки. Белая стрелка.
    "selfIconAlpha": 100,
    // Camera transparency and its attached geometry (green triangle).
    // Прозрачность камеры и прикрепленной геометрии (зеленый треугольник).
    "cameraAlpha": 100,
    // Vehicles icon size. Does not affect attached geometry and textfields. Floating point allowed: 0.7, 1.4.
    // Размер иконки техники. Не влияет на прикрепленную к геометрию и текстовые поля. Можно дробные: 0.7, 1.4.
    "iconScale": 0.75,
    // Map zoom by key pressing. Key is defined at file "hotkeys.xc".
    // Увеличение миникарты по нажатию кнопки. Кнопка задается в файле "hotkeys.xc".
    "zoom": {
      // Number of pixels to get back from maximum size (screen height-minimap height).
      // Число пикселей для уменьшения миникарты от максимального размера (высота экрана-высота миникарты).
      "pixelsBack": 160,
      // false - does not set zoomed minimap at display center.
      // false - не устанавливать увеличенную миникарту по центру экрана.
      "centered": true
    },
    // Minimap circles.
    // Круги на миникарте.
    "circles": ${"../tankrange.xc":"circles"},
    "square" : { // Квадрат со стороной 1000m. Показывает границы максимальной отрисовка юнитов.
      "enabled": false,
      // Show square if using artillery\SPG vehicle.
      // Показывать ли квадрат в случае артиллерии.
      "artilleryEnabled": false,
      // Толщина линии.
      "thickness": 0.7,
      // Прозрачность.
      "alpha": 40,
      // Цвет.
      "color": "0xFFFFFF"
    }
  }
}
