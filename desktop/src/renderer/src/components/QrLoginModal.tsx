import React, { useEffect, useRef, useState } from 'react'
import { Loader2, Check, RotateCcw } from 'lucide-react'
import { t } from '../i18n'
import apiClient from '../api/client'
import { Modal } from '../pages/settings/primitives'

type Provider = 'weixin' | 'wechat_group' | 'feishu'
type Phase = 'loading' | 'waiting' | 'scanned' | 'success' | 'error'

interface QrLoginModalProps {
  provider: Provider
  onClose: () => void
  // Fired once the channel is connected so the page can refresh.
  onConnected: () => void
}

const POLL_INTERVAL = 2000

// Shared QR-login / QR-register modal for WeChat and Feishu. Mirrors the web
// console flow: fetch a QR, poll status, then connect the channel on success.
const QrLoginModal: React.FC<QrLoginModalProps> = ({ provider, onClose, onConnected }) => {
  const [phase, setPhase] = useState<Phase>('loading')
  const [qr, setQr] = useState('')
  const [openLink, setOpenLink] = useState('')
  const [errMsg, setErrMsg] = useState('')
  const [wechatGroupRecoveryMsg, setWechatGroupRecoveryMsg] = useState('')
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const aliveRef = useRef(true)

  const stopPoll = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const fail = (msg: string) => {
    if (!aliveRef.current) return
    setPhase('error')
    setErrMsg(msg)
  }

  const updateWechatGroupRecovery = (data: { extra?: { identity_recovery?: { requires_confirmation?: boolean; pending_count?: number } } }) => {
    const recovery = data.extra?.identity_recovery
    if (recovery?.requires_confirmation) {
      const count = Number(recovery.pending_count || 0)
      setWechatGroupRecoveryMsg(t('wechat_group_identity_recovery_pending').replace('{count}', String(count)))
    } else {
      setWechatGroupRecoveryMsg('')
    }
  }

  // ---- WeChat: GET qr, POST poll {scaned|confirmed|expired} -----------------
  const pollWeixin = () => {
    timerRef.current = setTimeout(async () => {
      if (!aliveRef.current) return
      try {
        const data = await apiClient.weixinQrAction('poll')
        if (!aliveRef.current) return
        if (data.status !== 'success') return pollWeixin()
        const s = data.qr_status as string
        if (s === 'confirmed') {
          setPhase('success')
          await apiClient.channelAction('connect', 'weixin', {})
          if (aliveRef.current) onConnected()
        } else if (s === 'expired' && (data.qr_image || data.qrcode_url)) {
          setQr((data.qr_image as string) || (data.qrcode_url as string))
          setPhase('waiting')
          pollWeixin()
        } else if (s === 'scaned') {
          setPhase('scanned')
          pollWeixin()
        } else {
          pollWeixin()
        }
      } catch {
        pollWeixin()
      }
    }, POLL_INTERVAL)
  }

  const startWeixin = async () => {
    setPhase('loading')
    try {
      const data = await apiClient.getWeixinQr()
      if (!aliveRef.current) return
      if (data.status !== 'success') return fail(data.message || t('weixin_scan_fail'))
      setQr(data.qr_image || data.qrcode_url || '')
      setPhase('waiting')
      pollWeixin()
    } catch {
      fail(t('weixin_scan_fail'))
    }
  }

  const pollWechatGroup = () => {
    timerRef.current = setTimeout(async () => {
      if (!aliveRef.current) return
      try {
        const data = await apiClient.wechatGroupQrAction('poll')
        if (!aliveRef.current) return
        if (data.status !== 'success') return pollWechatGroup()
        const s = data.login_status as string
        if (s === 'logged_in' || s === 'connected') {
          updateWechatGroupRecovery(data)
          setPhase('success')
          if (aliveRef.current) onConnected()
        } else if (data.qr_image || data.qrcode_url) {
          setQr((data.qr_image as string) || (data.qrcode_url as string))
          setPhase('waiting')
          pollWechatGroup()
        } else {
          pollWechatGroup()
        }
      } catch {
        pollWechatGroup()
      }
    }, POLL_INTERVAL)
  }

  const startWechatGroup = async () => {
    setPhase('loading')
    try {
      await apiClient.channelAction('connect', 'wechat_group', {})
      if (!aliveRef.current) return
      const data = await apiClient.getWechatGroupQr()
      if (!aliveRef.current) return
      if (data.status !== 'success') return fail(data.message || t('wechat_group_scan_fail'))
      if (data.qr_image || data.qrcode_url) {
        setQr(data.qr_image || data.qrcode_url || '')
      }
      updateWechatGroupRecovery(data)
      setPhase('waiting')
      pollWechatGroup()
    } catch {
      fail(t('wechat_group_scan_fail'))
    }
  }

  // ---- Feishu: GET qr, POST poll {done|expired|denied|error} ----------------
  const pollFeishu = () => {
    timerRef.current = setTimeout(async () => {
      if (!aliveRef.current) return
      try {
        const data = await apiClient.feishuRegisterPoll()
        if (!aliveRef.current) return
        if (data.status !== 'success') return fail((data.message as string) || t('feishu_scan_fail'))
        const rs = data.register_status as string
        if (rs === 'done') {
          setPhase('success')
          await apiClient.channelAction('connect', 'feishu', {
            feishu_app_id: data.app_id,
            feishu_app_secret: data.app_secret,
          })
          if (aliveRef.current) onConnected()
        } else if (rs === 'expired') {
          fail(t('feishu_scan_expired'))
        } else if (rs === 'denied') {
          fail(t('feishu_scan_denied'))
        } else if (rs === 'error') {
          fail((data.message as string) || t('feishu_scan_fail'))
        } else {
          pollFeishu()
        }
      } catch {
        pollFeishu()
      }
    }, POLL_INTERVAL)
  }

  const startFeishu = async () => {
    setPhase('loading')
    try {
      const data = await apiClient.getFeishuRegister()
      if (!aliveRef.current) return
      if (data.status !== 'success') return fail(data.message || t('feishu_scan_fail'))
      setQr(data.qr_image || data.qrcode_url || '')
      setOpenLink(data.qrcode_url || '')
      setPhase('waiting')
      pollFeishu()
    } catch {
      fail(t('feishu_scan_fail'))
    }
  }

  const start = () => {
    stopPoll()
    if (provider === 'weixin') void startWeixin()
    else if (provider === 'wechat_group') void startWechatGroup()
    else void startFeishu()
  }

  useEffect(() => {
    aliveRef.current = true
    start()
    return () => {
      aliveRef.current = false
      stopPoll()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider])

  const title = provider === 'feishu'
    ? t('feishu_scan_title')
    : provider === 'wechat_group'
      ? t('wechat_group_scan_title')
      : t('weixin_scan_title')
  const desc = provider === 'feishu'
    ? t('feishu_scan_desc')
    : provider === 'wechat_group'
      ? t('wechat_group_scan_desc')
      : t('weixin_scan_desc')
  const tip = provider === 'feishu'
    ? t('feishu_scan_tip')
    : provider === 'wechat_group'
      ? t('wechat_group_qr_tip')
      : t('weixin_qr_tip')

  const statusText = (): string => {
    if (provider === 'weixin' || provider === 'wechat_group') {
      if (phase === 'scanned') return t('weixin_scan_scanned')
      return provider === 'wechat_group' ? t('wechat_group_scan_waiting') : t('weixin_scan_waiting')
    }
    return t('feishu_scan_waiting')
  }

  return (
    <Modal open title={title} onClose={onClose}>
      <div className="flex flex-col items-center py-2">
        {phase === 'loading' && (
          <div className="flex items-center text-content-tertiary py-10">
            <Loader2 size={18} className="animate-spin mr-2" />
            {provider === 'feishu' ? t('feishu_scan_loading') : provider === 'wechat_group' ? t('wechat_group_scan_loading') : t('weixin_scan_loading')}
          </div>
        )}

        {(phase === 'waiting' || phase === 'scanned') && (
          <>
            <p className="text-sm text-content-secondary mb-4 text-center">{desc}</p>
            <div className="bg-white p-3 rounded-card border border-subtle mb-3">
              {qr ? (
                <img src={qr} alt="QR" className="w-48 h-48" style={{ imageRendering: 'pixelated' }} />
              ) : (
                <div className="w-48 h-48 flex items-center justify-center text-content-tertiary text-xs">QR</div>
              )}
            </div>
            <p className={`text-xs mb-1 ${phase === 'scanned' ? 'text-accent' : 'text-warning'}`}>{statusText()}</p>
            <p className="text-xs text-content-tertiary">{tip}</p>
            {openLink && (
              <a
                href={openLink}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-info hover:underline mt-2"
              >
                {t('feishu_scan_open_link')}
              </a>
            )}
          </>
        )}

        {phase === 'success' && (
          <div className="flex flex-col items-center py-8">
            <div className="w-12 h-12 rounded-full bg-accent-soft flex items-center justify-center mb-3">
              <Check size={22} className="text-accent" />
            </div>
            <p className="text-sm font-medium text-accent">
              {provider === 'feishu'
                ? t('feishu_scan_success')
                : provider === 'wechat_group'
                  ? t('wechat_group_scan_success')
                  : t('weixin_scan_success')}
            </p>
            {provider === 'wechat_group' && wechatGroupRecoveryMsg && (
              <p className="mt-2 text-xs text-warning text-center max-w-xs">{wechatGroupRecoveryMsg}</p>
            )}
          </div>
        )}

        {phase === 'error' && (
          <div className="flex flex-col items-center py-8">
            <p className="text-sm text-danger text-center mb-3">{errMsg}</p>
            <button
              onClick={start}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-btn border border-strong text-sm text-content-secondary hover:bg-inset cursor-pointer transition-colors"
            >
              <RotateCcw size={13} />
              {t('feishu_scan_retry')}
            </button>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default QrLoginModal
