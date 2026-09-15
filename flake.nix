{
  description = "JoinQuant daily check-in development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f {
        pkgs = import nixpkgs { inherit system; };
      });
      pythonFor = pkgs: pkgs.python312.withPackages (pythonPackages: with pythonPackages; [
        numpy
        pillow
        scipy
      ]);
      packageFor = pkgs:
        let
          python = pythonFor pkgs;
          runtimeSource = pkgs.lib.fileset.toSource {
            root = ./.;
            fileset = pkgs.lib.fileset.unions [
              ./captcha_solver.py
              ./checkin.mjs
              (pkgs.lib.fileset.fileFilter (file: file.hasExt "py") ./src)
            ];
          };
        in pkgs.writeShellApplication {
          name = "autojoinquant";
          runtimeInputs = [ pkgs.nodejs_22 python ]
            ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [ pkgs.chromium ];
          text = ''
            export PYTHONPATH="${runtimeSource}/src''${PYTHONPATH:+:$PYTHONPATH}"
            export AUTOJOINQUANT_EXECUTABLE="$0"
            export JOINQUANT_NODE_BIN="${pkgs.nodejs_22}/bin/node"
            export JOINQUANT_PYTHON="${python}/bin/python"
            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              export JOINQUANT_CHROME_BIN="${pkgs.chromium}/bin/chromium"
            ''}
            exec "${python}/bin/python" -m autojoinquant "$@"
          '';
        };
    in {
      packages = forAllSystems ({ pkgs }: {
        default = packageFor pkgs;
      });

      apps = forAllSystems ({ pkgs }: {
        default = {
          type = "app";
          program = "${packageFor pkgs}/bin/autojoinquant";
        };
      });

      checks = forAllSystems ({ pkgs }:
        let
          python = pkgs.python312.withPackages (pythonPackages: with pythonPackages; [
            numpy
            pillow
            pytest
            ruff
            scipy
          ]);
          checkSource = pkgs.lib.fileset.toSource {
            root = ./.;
            fileset = pkgs.lib.fileset.unions [
              ./captcha_solver.py
              ./checkin.mjs
              ./pyproject.toml
              (pkgs.lib.fileset.fileFilter (file: file.hasExt "py") ./src)
              (pkgs.lib.fileset.fileFilter (file: file.hasExt "py") ./tests)
            ];
          };
        in {
          quality = pkgs.runCommand "autojoinquant-quality" {
            nativeBuildInputs = [ pkgs.nodejs_22 python ];
          } ''
            cp -R ${checkSource} source
            chmod -R u+w source
            cd source
            node --check checkin.mjs
            python -m ruff check .
            python -m pytest
            touch "$out"
          '';
        });

      devShells = forAllSystems ({ pkgs }: {
        default = pkgs.mkShell {
          packages = [
            pkgs.python312
            pkgs.uv
            pkgs.nodejs_22
          ] ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
            pkgs.chromium
          ];
          shellHook = ''
            echo "JoinQuant check-in development shell"
            echo "Run: uv sync && uv run pytest"
            ${pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''
              export JOINQUANT_CHROME_BIN="${pkgs.chromium}/bin/chromium"
              echo "JOINQUANT_CHROME_BIN=$JOINQUANT_CHROME_BIN"
            ''}
          '';
        };
      });
    };
}
