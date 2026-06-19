import { prisma } from "../lib/prisma";

async function verify() {
  try {
    const userCount = await prisma.user.count();
    console.log(`✅ Connected. Found ${userCount} users in the database.`);
  } catch (error) {
    console.error("❌ Connection failed!");
    console.error(error);
    process.exit(1);
  }
}

verify();
