cask "broadlinkac" do
  version "3A"
  sha256 :no_check  # 每次构建 SHA256 会变，用户下载后自行替换

  url "https://github.com/oywq00008-cell/BroadlinkAC-For-Agent/releases/latest/download/BroadlinkAC.app.zip",
      verified: "github.com/oywq00008-cell/BroadlinkAC-For-Agent/"
  name "BroadlinkAC"
  desc "AI-powered smart AC controller with Broadlink IR blaster"
  homepage "https://github.com/oywq00008-cell/BroadlinkAC-For-Agent"

  depends_on macos: ">= :catalina"

  app "BroadlinkAC.app"

  # 未签名应用需要清除隔离标记
  installer manual: "BroadlinkAC.app"

  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-cr", "#{appdir}/BroadlinkAC.app"],
                   sudo: false
  end

  zap trash: [
    "~/Library/Application Support/BroadlinkAC",
    "~/.ac_controller",
  ]
end
