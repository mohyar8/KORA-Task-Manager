import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Building2, Crown, MessageSquare, Users } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import { Modal } from '@/shared/ui/Modal'
import { useSession } from '@/features/auth/session'
import { useDisplayName } from '@/features/members/directory'
import { dmChannelId } from '@/mock/chatStore'
import { mockOrg, type OrgNode, type OrgPerson } from '@/mock/orgChart'
import { workUnits } from '@/features/teams/units'
import { teamColor } from '@/features/teams/teamColor'
import styles from './structure.module.css'

interface Picked {
  person: OrgPerson
  node: OrgNode
  leader: boolean
}

/** The whole organization as a top-down chart. Everyone sees all of it; your own unit is highlighted. Click anyone to message them. */
export function StructurePage() {
  const { t } = useI18n()
  const { access, account } = useSession()
  const displayName = useDisplayName()
  const myNames = useMemo(() => new Set(workUnits(access).map((u) => u.name)), [access])
  const me = account?.member_id ?? ''
  const [picked, setPicked] = useState<Picked | null>(null)
  const mine = useRef<HTMLDivElement | null>(null)

  // The signed-in person appears as a member of their own team in the mock tree.
  const tree = useMemo(() => {
    const addMe = (n: OrgNode): OrgNode => ({
      ...n,
      members: me && n.kind === 'team' && myNames.has(n.name) && displayName ? [...n.members, { id: me, name: displayName }] : n.members,
      children: n.children.map(addMe),
    })
    return addMe(mockOrg)
  }, [me, myNames, displayName])

  useEffect(() => { mine.current?.scrollIntoView?.({ block: 'center', inline: 'center' }) }, [tree])

  const role = (n: OrgNode, leader: boolean) => (leader ? t(`structure.leaderOf.${n.kind}` as 'structure.leaderOf.team', { unit: n.name }) : t('structure.memberOf', { unit: n.name }))

  const render = (n: OrgNode, depth: number) => {
    const isMine = myNames.has(n.name)
    const Icon = n.kind === 'organization' ? Crown : n.kind === 'administration' ? Building2 : Users
    return (
      <li key={n.id}>
        <div ref={isMine ? mine : undefined} className={`${styles.unit} ${isMine ? styles.mineUnit : ''} ${depth === 0 ? styles.root : ''}`} style={{ ['--unit' as string]: teamColor(n.id) }} role="group" aria-label={n.name}>
          <header>
            <Icon size={16} aria-hidden="true" />
            <h2>{n.name}</h2>
            {isMine && <span className={styles.badge}>{t('structure.mine')}</span>}
          </header>
          <span className={styles.kind}>{t(`structure.kind.${n.kind}` as 'structure.kind.team')}</span>
          {n.leader && (
            <button type="button" className={`${styles.leader} ${n.leader.id === me ? styles.me : ''}`} aria-pressed={picked?.person.id === n.leader.id} onClick={() => setPicked({ person: n.leader!, node: n, leader: true })}>
              <span className={styles.avatar} aria-hidden="true">{n.leader.name.charAt(0)}</span>
              <span className={styles.who}>
                <small>{t('structure.responsible')}</small>
                <b>{n.leader.name}</b>
              </span>
            </button>
          )}
          {n.members.length > 0 && (
            <ul className={styles.members} aria-label={t('structure.members')}>
              {n.members.map((m) => (
                <li key={m.id}>
                  <button type="button" className={`${styles.member} ${m.id === me ? styles.me : ''}`} aria-pressed={picked?.person.id === m.id} onClick={() => setPicked({ person: m, node: n, leader: false })}>
                    <span className={styles.dot} aria-hidden="true">{m.name.charAt(0)}</span>
                    {m.name}{m.id === me && <i> ({t('structure.you')})</i>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {n.children.length > 0 && <ul>{n.children.map((c) => render(c, depth + 1))}</ul>}
      </li>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.treeWrap}>
        <h1 className={styles.title}>{t('structure.title')}</h1>
        <p className={styles.sub}>{t('structure.description')}</p>
        <ul className={styles.chart}>{render(tree, 0)}</ul>
      </div>
      <Modal open={!!picked} title={picked?.person.name ?? ''} onClose={() => setPicked(null)}>
        {picked && (
          <div className={styles.card}>
            <span className={styles.bigAvatar} style={{ background: teamColor(picked.node.id) }} aria-hidden="true">{picked.person.name.charAt(0)}</span>
            <p className={styles.cardRole}>{role(picked.node, picked.leader)}</p>
            <p className={styles.cardUnit}>{picked.node.name} · {t(`structure.kind.${picked.node.kind}` as 'structure.kind.team')}</p>
            {picked.person.id !== me && (
              <Link className={styles.message} to={`/chat/${dmChannelId(picked.person.id)}`}><MessageSquare size={18} aria-hidden="true" /> {t('chat.message')}</Link>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
