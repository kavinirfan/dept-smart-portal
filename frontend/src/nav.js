// Sidebar entries and which roles see them. Set `ready: false` to show a module as "coming soon".
export const NAV = [
  { path: '/', label: 'Home', roles: ['student', 'teacher', 'lab_incharge', 'admin'], ready: true },
  { path: '/marks', label: 'Marks', roles: ['student', 'teacher', 'admin'], ready: true },
  { path: '/labs', label: 'Lab Booking', roles: ['teacher', 'lab_incharge', 'admin'], ready: true },
  { path: '/faculty', label: 'Faculty Availability', roles: ['student', 'teacher', 'lab_incharge', 'admin'], ready: true },
  { path: '/notices', label: 'Jobs & Internships', roles: ['student', 'teacher', 'lab_incharge', 'admin'], ready: true },
  { path: '/chat', label: 'Campus Chat', roles: ['student', 'teacher', 'lab_incharge', 'admin'], ready: true },
  { path: '/dashboard', label: 'HOD Dashboard', roles: ['admin'], ready: true },
  { path: '/admin/users', label: 'Users', roles: ['admin'], ready: true },
  { path: '/admin/verification', label: 'ID Checks & Reports', roles: ['admin'], ready: true },
  { path: '/admin/subjects', label: 'Subjects & Credentials', roles: ['admin'], ready: true },
  { path: '/admin/audit', label: 'Audit Log', roles: ['admin'], ready: true },
  { path: '/profile', label: 'My Profile', roles: ['student', 'teacher', 'lab_incharge', 'admin'], ready: true },
]

export const navFor = (role) => NAV.filter((n) => n.roles.includes(role))
