import { prisma } from "../lib/prisma";

async function main() {
  console.log("Seeding started...");

  // Clean existing data
  await prisma.post.deleteMany();
  await prisma.user.deleteMany();

  // Create starter users and posts
  const user1 = await prisma.user.create({
    data: {
      email: "alice@example.com",
      name: "Alice",
      posts: {
        create: [
          {
            title: "Exploring Prisma Postgres",
            content: "Prisma Postgres is awesome and incredibly fast!",
            published: true,
          },
          {
            title: "TypeScript Best Practices",
            content: "Using typescript makes coding reliable.",
            published: true,
          },
        ],
      },
    },
  });

  const user2 = await prisma.user.create({
    data: {
      email: "bob@example.com",
      name: "Bob",
      posts: {
        create: [
          {
            title: "FastAPI and Python",
            content: "Building swift backend APIs with python is simple.",
            published: true,
          },
        ],
      },
    },
  });

  console.log("Seeding completed successfully!");
  console.log(`Created users: ${user1.name} and ${user2.name}`);
}

main()
  .catch((e) => {
    console.error("Error during seed:", e);
    process.exit(1);
  });
