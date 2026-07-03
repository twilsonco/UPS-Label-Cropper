# Changelog

## [1.1.1](https://github.com/twilsonco/UPS-Label-Cropper/compare/v1.1.0...v1.1.1) (2026-07-03)


### Bug Fixes

* ci optimization ([d228d17](https://github.com/twilsonco/UPS-Label-Cropper/commit/d228d17f981ab5d5375858cb9ad3ae5ffc3ef8d9))

## [1.1.0](https://github.com/twilsonco/UPS-Label-Cropper/compare/v1.0.0...v1.1.0) (2026-07-01)


### Features

* add first run settings dialog ([607623e](https://github.com/twilsonco/UPS-Label-Cropper/commit/607623e941348b34935b9375e0a404a31fb3f200))
* add quit flag to gracefully exit tray loop ([3df0c83](https://github.com/twilsonco/UPS-Label-Cropper/commit/3df0c835cd110f5fd6663bc3de61fe553d2770c6))
* Add support for silent PDF printing with SumatraPDF and improve file handling ([2f83f4c](https://github.com/twilsonco/UPS-Label-Cropper/commit/2f83f4cf8d513b2a8a6426a092e56a47c7aadbef))
* Add ups-watch.bat script for Windows watch mode execution ([75052ed](https://github.com/twilsonco/UPS-Label-Cropper/commit/75052edb9c9f4e1bb64dd288620f0e22a970ad08))
* Add ups-watch.vbs script for hidden watcher execution on Windows ([c8b35b1](https://github.com/twilsonco/UPS-Label-Cropper/commit/c8b35b1f9983cee0df6a819d5441f38b4571e018))
* Enhance logging and configuration visibility in watch mode and processing pipeline ([18bb9d5](https://github.com/twilsonco/UPS-Label-Cropper/commit/18bb9d51f56e7b08b684cdb49a004309892f637c))
* Enhance ups-watch.vbs with logging and error handling for startup process ([4d55197](https://github.com/twilsonco/UPS-Label-Cropper/commit/4d55197fccee2344198a4302b647ca504d707ae2))
* Implement auto-process and print UPS labels ([81805f9](https://github.com/twilsonco/UPS-Label-Cropper/commit/81805f90b0115be7e617ee885ae464dc7275d7f8))
* Implement settings dialog for user configuration and log file access ([dcce65e](https://github.com/twilsonco/UPS-Label-Cropper/commit/dcce65efc2bcff86b4f260c16dddc33d37a25549))
* Implement watcher restart functionality on settings change ([315b3eb](https://github.com/twilsonco/UPS-Label-Cropper/commit/315b3ebc05f6d4834dd575645786790875f8891d))
* Improve settings dialog by handling focus issues on macOS during directory selection and validation ([9d2aa77](https://github.com/twilsonco/UPS-Label-Cropper/commit/9d2aa77347e35e94d19c1b8593b736a302f0d243))
* precompile Windows exe with autostart option ([f5938f5](https://github.com/twilsonco/UPS-Label-Cropper/commit/f5938f5556d779e19f6a4fb14cc559dea630c09d))
* Update tray icon creation to load from assets instead of hardcoded image ([b6b7cb3](https://github.com/twilsonco/UPS-Label-Cropper/commit/b6b7cb325b9da4e9bd75e78ae2cf22ef41337d71))


### Bug Fixes

* **ci:** update pyinstaller data path scope ([7c32723](https://github.com/twilsonco/UPS-Label-Cropper/commit/7c327237036ec5e1ffcdc4b4dff101d6b3142755))
* **cli:** exit if input/output pdf args are missing ([237ecfb](https://github.com/twilsonco/UPS-Label-Cropper/commit/237ecfbe20fa7530343cadde7da28bcad91a5508))
* default to watch mode when no files specified ([17e7d2e](https://github.com/twilsonco/UPS-Label-Cropper/commit/17e7d2e9cafd48c0d71201747c8ccfa4c7eb9651))
* **tray:** fix nested event loop on windows ([117dd71](https://github.com/twilsonco/UPS-Label-Cropper/commit/117dd719b10170e7db16b78d8a35ed9650c68139))
* **tray:** prevent crash on quit by avoiding direct systray.shutdown() ([2313b79](https://github.com/twilsonco/UPS-Label-Cropper/commit/2313b7990d661e8371c6788d442e3cb22852a054))
* **tray:** resolve click events and run icon in main thread ([95fef74](https://github.com/twilsonco/UPS-Label-Cropper/commit/95fef741cc43d841935719c7ed92628723e6fbf8))
* **tray:** simplify quit loop and cleanup systray logic ([e1cc72f](https://github.com/twilsonco/UPS-Label-Cropper/commit/e1cc72f10f34b5ced1d7c684c4a5f1db5201e98f))
* **tray:** switch icon.run to run_detached ([e2d70ac](https://github.com/twilsonco/UPS-Label-Cropper/commit/e2d70acdf376883c67c402326e2cb24ba224b100))
* **tray:** use base path helper for icon resolution ([d29a002](https://github.com/twilsonco/UPS-Label-Cropper/commit/d29a002d5b39bfbf738e42948c986168fdee8341))
* **tray:** use local flag instead of global for quit logic ([3ed9434](https://github.com/twilsonco/UPS-Label-Cropper/commit/3ed9434fc100bc38f64aa5969f7bb286ce3c7bd3))


### Documentation

* Reintroduce first run details in README for watch mode setup ([17ee366](https://github.com/twilsonco/UPS-Label-Cropper/commit/17ee3660e1ea7d15ece216ac5f93952ecb7eb347))
* simplify install guide and remove source setup ([b59fc5e](https://github.com/twilsonco/UPS-Label-Cropper/commit/b59fc5ed22de301675e0a04622bb89472425cf03))
* Update README with batch file usage for Windows watch mode setup ([6524351](https://github.com/twilsonco/UPS-Label-Cropper/commit/65243510c11f152a8c5862ef967eb38779566e03))
* Update README with detailed Windows setup instructions and prerequisites ([710a585](https://github.com/twilsonco/UPS-Label-Cropper/commit/710a585addd7bcc7caf1f4c9c9a4cf0ea9a5f738))
* update watch mode help text for clarity ([7e0ba27](https://github.com/twilsonco/UPS-Label-Cropper/commit/7e0ba27bbb8fb6b482308f101c006dba97f00f85))
* Update Windows setup instructions for watch mode with batch file workaround ([b3e203c](https://github.com/twilsonco/UPS-Label-Cropper/commit/b3e203ccd4a23ce3f312086a77e79c403fd6e9d8))
