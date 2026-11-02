/**
 * MOCK: the whole organization as a tree, the same for everyone who signs in.
 * The backend will serve this shape (units with their leader and members) from one endpoint.
 */
export interface OrgPerson {
  id: string
  name: string
}

export type OrgKind = 'organization' | 'administration' | 'team'

export interface OrgNode {
  id: string
  name: string
  kind: OrgKind
  leader: OrgPerson | null
  members: OrgPerson[]
  children: OrgNode[]
}

const p = (id: string, name: string): OrgPerson => ({ id: `mock-${id}`, name })

export const mockOrg: OrgNode = {
  id: 'org',
  name: 'كورة',
  kind: 'organization',
  leader: p('khaled', 'خالد العتيبي'),
  members: [p('noura', 'نورة السبيعي')],
  children: [
    {
      id: 'pmo', name: 'إدارة المشاريع', kind: 'administration', leader: p('majed', 'ماجد الحربي'), members: [p('rana', 'رنا الزهراني')],
      children: [],
    },
    {
      id: 'media', name: 'إدارة الإعلام', kind: 'administration', leader: p('sultan', 'سلطان القحطاني'), members: [p('lama', 'لمى الغامدي')],
      children: [
        { id: 'design', name: 'فريق التصميم', kind: 'team', leader: p('omar', 'عمر الشهري'), members: [p('hind', 'هند العسيري'), p('fahad', 'فهد المالكي'), p('dana', 'دانة الشمري')], children: [] },
        { id: 'content', name: 'فريق المحتوى', kind: 'team', leader: p('maha', 'مها الدوسري'), members: [p('yazeed', 'يزيد العنزي'), p('reem', 'ريم الحازمي')], children: [] },
        { id: 'video', name: 'فريق المونتاج', kind: 'team', leader: p('turki', 'تركي البقمي'), members: [p('abeer', 'عبير الرشيدي')], children: [] },
      ],
    },
    {
      id: 'ops', name: 'إدارة العمليات', kind: 'administration', leader: p('nasser', 'ناصر الجهني'), members: [p('salma', 'سلمى القرني')],
      children: [
        { id: 'logistics', name: 'فريق اللوجستيات', kind: 'team', leader: p('badr', 'بدر الأحمدي'), members: [p('joud', 'جود السلمي'), p('ziyad', 'زياد الحربي')], children: [] },
        { id: 'volunteers', name: 'فريق المتطوعين', kind: 'team', leader: p('ghada', 'غادة المطيري'), members: [p('saud', 'سعود العمري'), p('nada', 'ندى الثبيتي')], children: [] },
      ],
    },
  ],
}

export function flattenPeople(node: OrgNode = mockOrg): OrgPerson[] {
  return [...(node.leader ? [node.leader] : []), ...node.members, ...node.children.flatMap((c) => flattenPeople(c))]
}

export const mockPersonName = (id: string): string | undefined => flattenPeople().find((x) => x.id === id)?.name
